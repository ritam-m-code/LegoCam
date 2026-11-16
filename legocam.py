"""Capture, calibrate and validate planar silhouette dimensions."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

import cv2
import numpy as np

from vision import detect, select


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def references():
    with Path(__file__).with_name("reference_blocks.csv").open(
        newline="", encoding="utf-8-sig"
    ) as stream:
        return {
            r["block_id"]: {k: float(r[k]) for k in ("length_mm", "width_mm", "height_mm")}
            for r in csv.DictReader(stream)
        }


def corrected_vectors(observation, radial_k=0):
    vectors = np.asarray(observation["vectors"], dtype=float)
    if radial_k == 0:
        return vectors
    size = np.asarray(observation["image_size"], dtype=float)
    centre = np.asarray(observation["centre_px"]) - size / 2
    start = centre - vectors / 2
    end = centre + vectors / 2

    def correct(points):
        radius_squared = np.sum((points / max(size)) ** 2, axis=1)
        if np.any(1 + 3 * radial_k * radius_squared <= 0):
            raise ValueError("Radial correction is not monotonic in the observed area")
        return points * (1 + radial_k * radius_squared[:, None])

    return correct(end) - correct(start)


def dimensions(observation, scales, radial_k=0):
    return np.linalg.norm(corrected_vectors(observation, radial_k) * np.asarray(scales), axis=1)


def fit_metric(groups, radial_k=0):
    """Fit positive horizontal/vertical scales from independent placement means."""
    matrix, target = [], []
    for group in groups:
        squared = np.mean(
            [corrected_vectors(o, radial_k) ** 2 for o in group["observations"]], axis=0
        )
        # Use long dimensions only: nearly square cross-sections can be placed on either face.
        matrix.append(squared[0])
        target.append(group["reference"]["length_mm"] ** 2)
    matrix, target = np.asarray(matrix), np.asarray(target)
    if np.linalg.matrix_rank(matrix) < 2 or np.linalg.cond(matrix / target[:, None]) > 20:
        raise ValueError("Capture a short reference vertically as well as horizontal references")
    # Relative weighting prevents long artifacts completely dominating short edges.
    coefficients, *_ = np.linalg.lstsq(matrix / target[:, None], np.ones_like(target), rcond=None)
    if np.any(coefficients <= 0):
        raise ValueError("Nonphysical scales; inspect outlines and references")
    return np.sqrt(coefficients)


def records(root):
    return [read_json(path) for path in sorted((root / "records").glob("*.json"))]


def validation_checks(root, rows):
    """Use the latest completed check pass; keep unfinished passes as raw evidence."""
    checks = [row for row in rows if row["role"] == "validation"]
    for path in sorted(root.glob("checks_*.json"), reverse=True):
        progress = read_json(path)
        plan = progress.get("plan", [])
        completed = progress.get("completed", [])
        if plan and progress.get("step") == len(plan) and len(completed) == len(plan):
            selected = [row for row in checks if row["id"] in completed]
            if len(selected) == len(completed):
                return selected, "latest completed pass: " + path.name
    return checks, "all recorded validation captures"


def capture(root, args):
    config = read_json(root / "setup.json")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        raise ValueError("Use letters, numbers, underscore or hyphen for labels")
    refs = references()
    if args.role != "measurement" and args.block not in refs:
        raise ValueError("Reference capture requires a known --block, e.g. B100")
    if args.frames < 2:
        raise ValueError("Capture at least two frames")
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + "_" + args.label
    folder = root / "images" / identifier
    folder.mkdir(parents=True)
    cap = cv2.VideoCapture(config["camera"], cv2.CAP_MSMF)
    images, observations = [], []
    try:
        if not cap.isOpened():
            raise ValueError("Cannot open camera; close other camera apps")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config["width"])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config["height"])
        cap.read()  # Start stream before applying controls.
        applied = {
            "auto_exposure": bool(cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)),
            "exposure": bool(cap.set(cv2.CAP_PROP_EXPOSURE, config["exposure"])),
            "gain": bool(cap.set(cv2.CAP_PROP_GAIN, config["gain"])),
        }
        for _ in range(5):
            cap.read()
        for index in range(args.frames):
            ok, image = cap.read()
            if not ok or image is None:
                raise ValueError("Camera stopped returning frames")
            if [image.shape[1], image.shape[0]] != [config["width"], config["height"]]:
                raise ValueError("Camera did not deliver configured resolution")
            path = folder / f"{index:03}.png"
            if not cv2.imwrite(str(path), image):
                raise ValueError("Image save failed")
            images.append(str(path.relative_to(root)))
            observations.append(detect(image, config["roi"]))
            time.sleep(0.1)
        readback = {
            "exposure": cap.get(cv2.CAP_PROP_EXPOSURE),
            "gain": cap.get(cv2.CAP_PROP_GAIN),
            "auto_exposure": cap.get(cv2.CAP_PROP_AUTO_EXPOSURE),
        }
    finally:
        cap.release()
    record = {
        "id": identifier,
        "label": args.label,
        "role": args.role,
        "block": args.block,
        "placement": args.placement,
        "setup_hash": setup_hash(config),
        "images": images,
        "observations": observations,
        "control_set_returned": applied,
        "control_readback": readback,
        "settings_verified": False,
    }
    if args.role != "measurement":
        record["reference"] = refs[args.block]
    save_json(root / "records" / (identifier + ".json"), record)
    overlay = image.copy()
    cv2.polylines(overlay, [np.asarray(observations[-1]["box"], np.int32)], True, (0, 255, 0), 3)
    cv2.drawMarker(
        overlay, (image.shape[1] // 2, image.shape[0] // 2), (0, 255, 255), cv2.MARKER_CROSS, 70, 3
    )
    cv2.imwrite(str(folder / "overlay.png"), overlay)
    cv2.imwrite(str(root / "latest_preview.jpg"), cv2.resize(overlay, (960, 758)))
    print(
        json.dumps(
            {
                "record": identifier,
                "frames": len(observations),
                "mean_pixels": np.mean(
                    [[o["length_px"], o["width_px"]] for o in observations], axis=0
                ).tolist(),
                "control_readback": readback,
                "warning": "Inspect overlay; driver control readback may be unreliable",
            },
            indent=2,
        )
    )


def setup_hash(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def fit(root, radial=False, verbose=True):
    config = read_json(root / "setup.json")
    groups = [
        r
        for r in records(root)
        if r["role"] == "calibration" and r["setup_hash"] == setup_hash(config)
    ]
    if len({r["block"] for r in groups}) < 4:
        raise ValueError("Capture at least four different calibration blocks")
    radial_k = 0.0
    scales = fit_metric(groups)
    if radial:

        def candidate(k):
            candidate_scales = fit_metric(groups, k)
            relative_errors = [
                (
                    np.mean([dimensions(o, candidate_scales, k)[0] for o in r["observations"]])
                    / r["reference"]["length_mm"]
                    - 1
                )
                for r in groups
            ]
            return float(np.mean(np.square(relative_errors))), k, candidate_scales

        candidates = []
        for k in np.linspace(-2, 4, 301):
            try:
                candidates.append(candidate(float(k)))
            except ValueError:
                continue
        if not candidates:
            raise ValueError("Cannot fit radial correction")
        _, radial_k, scales = min(candidates, key=lambda item: item[0])
        _, radial_k, scales = min(
            (candidate(float(k)) for k in np.linspace(radial_k - 0.02, radial_k + 0.02, 41)),
            key=lambda item: item[0],
        )
    coverage = [[], []]
    for group in groups:
        for observation in group["observations"]:
            axis = int(np.argmax(np.abs(observation["vectors"][0])))
            coverage[axis].append(group["reference"]["length_mm"])
    errors = [
        np.mean([dimensions(o, scales, radial_k) for o in r["observations"]], axis=0)
        - np.array([r["reference"]["length_mm"], r["reference"]["width_mm"]])
        for r in groups
    ]
    model = {
        "schema": 1,
        "setup_hash": setup_hash(config),
        "scales_mm_per_px": scales.tolist(),
        "radial_k": radial_k,
        "radial_normalization": "image max dimension; centre fixed at image centre",
        "fit_record_ids": [r["id"] for r in groups],
        "fit_errors_mm": np.asarray(errors).tolist(),
        "axis_reference_ranges_mm": [
            [min(values), max(values)] if values else None for values in coverage
        ],
        "reference_height_range_mm": [
            min(r["reference"]["height_mm"] for r in groups),
            max(r["reference"]["height_mm"] for r in groups),
        ],
        "status": "PROVISIONAL until held-out validation and uncertainty budget are complete",
        "model": (
            "Diagonal metric with one radial correction fitted to long reference dimensions"
            if radial
            else "Diagonal planar metric fitted to long reference dimensions; no radial correction"
        )
        + "; no height compensation",
    }
    save_json(root / "calibration.json", model)
    save_json(root / ("calibration_radial.json" if radial else "calibration_baseline.json"), model)
    if verbose:
        print(json.dumps(model, indent=2))
    return model


def summarize(root, verbose=True):
    model = read_json(root / "calibration.json")
    config = read_json(root / "setup.json")
    if model["setup_hash"] != setup_hash(config):
        raise ValueError("Setup changed; recalibrate")
    scales = model["scales_mm_per_px"]
    output = []
    for record in records(root):
        if record["setup_hash"] != model["setup_hash"]:
            continue
        values = np.array(
            [dimensions(o, scales, model.get("radial_k", 0)) for o in record["observations"]]
        )
        row = {
            "id": record["id"],
            "label": record["label"],
            "role": record["role"],
            "block": record["block"],
            "placement": record["placement"],
            "frames": len(values),
        }
        warnings = (
            ["reference short-side comparison assumes recorded width face is visible"]
            if "reference" in record
            else []
        )
        if record.get("detection_roi", config["roi"]) != config["roi"]:
            warnings.append("detection region changed; verify against references")
        for edge_index, vector in enumerate(record["observations"][0]["vectors"]):
            axis = int(np.argmax(np.abs(vector)))
            bounds = model["axis_reference_ranges_mm"][axis]
            value = float(values[:, edge_index].mean())
            if bounds is None or value < bounds[0] - 0.5 or value > bounds[1] + 0.5:
                warnings.append(
                    f"{'length' if edge_index == 0 else 'width'} outside axis reference span"
                )
        row["warnings"] = "; ".join(warnings)
        for axis, name in enumerate(("length", "width")):
            row[name + "_mm"] = float(np.mean(values[:, axis]))
            row[name + "_frame_sd_mm"] = float(np.std(values[:, axis], ddof=1))
            row[name + "_error_mm"] = (
                row[name + "_mm"] - record["reference"][name + "_mm"]
                if "reference" in record
                else None
            )
        comparison_path = root / "comparisons" / (record["id"] + ".json")
        comparison = read_json(comparison_path) if comparison_path.exists() else {}
        for name in ("length", "width"):
            reading = comparison.get("caliper_" + name + "_mm")
            row["caliper_" + name + "_mm"] = reading
            row["caliper_" + name + "_error_mm"] = (
                row[name + "_mm"] - reading if reading is not None else None
            )
        output.append(row)
    if not output:
        raise ValueError("No compatible records")
    with (root / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    checks, validation_scope = validation_checks(root, output)
    fit_blocks = {r["block"] for r in output if r["role"] == "calibration"}
    independent = [r for r in checks if r["block"] not in fit_blocks]
    summary = {
        "calibration": model,
        "records": output,
        "validation_placements": len(checks),
        "validation_scope": validation_scope,
        "validation_record_ids": [row["id"] for row in checks],
        "held_out_block_ids": sorted({r["block"] for r in independent}),
        "uncertainty_status": "INCOMPLETE: no total expanded uncertainty is claimed",
    }
    for name in ("length", "width"):
        errors = np.array([r[name + "_error_mm"] for r in checks])
        summary[name + "_validation"] = (
            {
                "bias_mm": float(errors.mean()),
                "rmse_mm": float(np.sqrt(np.mean(errors**2))),
                "max_abs_error_mm": float(np.max(np.abs(errors))),
            }
            if errors.size
            else None
        )
    save_json(root / "summary.json", summary)
    lines = [
        "# LegoCam measurement results",
        "",
        model["status"],
        "",
        "Length and width are the long and short sides of a rotated silhouette rectangle.",
        "Calibration uses caliper-characterized reference artifacts, not certified gauge-block values.",
        "",
        f"Horizontal scale: {scales[0]:.8f} mm/pixel; vertical scale: {scales[1]:.8f} mm/pixel.",
        f"Validation placements: {len(checks)}; held-out block IDs: {', '.join(summary['held_out_block_ids']) or 'none'}.",
        "",
        "| Capture | Role | Length mm | Width mm | Length error mm | Width error mm |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in output:
        errors = [
            f"{row[n+'_error_mm']:+.3f}" if row[n + "_error_mm"] is not None else ""
            for n in ("length", "width")
        ]
        lines.append(
            f"| {row['label']} | {row['role']} | {row['length_mm']:.3f} | {row['width_mm']:.3f} | {errors[0]} | {errors[1]} |"
        )
    lines += [
        "",
        "## Uncertainty and limitations",
        "",
        "Frame standard deviations are saved in results.csv. They describe fixed-placement variation, not total accuracy. Consecutive frames may be correlated.",
        "A caliper accuracy limit of Â±0.02 mm corresponds to 0.0115 mm standard uncertainty only if a rectangular error distribution is justified. Shared reference error does not average away.",
        "A complete budget also requires reference reading/shape effects, fit uncertainty, repositioning, spatial distortion, height mismatch and drift. Validation RMSE is a performance diagnostic, not expanded uncertainty.",
        "The model description in calibration.json states whether a radial correction was fitted. No height correction is applied. Results outside tested size, location, orientation and height conditions are unvalidated.",
        "Camera control requests and reported settings are recorded, but the driver's readback has been inconsistent. Lock and verify settings before accepting calibration.",
    ]
    (root / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if verbose:
        print(
            json.dumps(
                {k: v for k, v in summary.items() if k not in ("records", "calibration")}, indent=2
            )
        )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="sessions/final_rig")
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("setup")
    setup.add_argument("image", help="Final-rig image for selecting the fixed measurement area")
    setup.add_argument("--roi", nargs=4, type=int)
    setup.add_argument("--camera", type=int, default=1)
    setup.add_argument("--exposure", type=float, default=-4)
    setup.add_argument("--gain", type=float, default=32)
    shot = sub.add_parser("capture")
    shot.add_argument("--label", required=True)
    shot.add_argument("--role", choices=["calibration", "validation", "measurement"], required=True)
    shot.add_argument("--block")
    shot.add_argument("--placement", default="centre-horizontal")
    shot.add_argument("--frames", type=int, default=5)
    fitter = sub.add_parser("fit")
    fitter.add_argument(
        "--radial",
        action="store_true",
        help="Fit one radial coefficient; requires independent validation",
    )
    sub.add_parser("results")
    args = parser.parse_args()
    root = Path(args.session)
    if args.command == "setup":
        if (root / "setup.json").exists():
            raise ValueError(
                "Session already configured; choose a new --session after hardware changes"
            )
        image = cv2.imread(args.image)
        if image is None:
            raise ValueError("Cannot read setup image")
        roi = args.roi or select(image)
        x, y, w, h = roi
        if min(x, y) < 0 or min(w, h) < 10 or x + w > image.shape[1] or y + h > image.shape[0]:
            raise ValueError("Invalid measurement area")
        config = {
            "camera": args.camera,
            "backend": "msmf",
            "width": image.shape[1],
            "height": image.shape[0],
            "roi": roi,
            "exposure": args.exposure,
            "gain": args.gain,
            "focus": "manual fixed",
            "created_utc": datetime.now(timezone.utc).isoformat(),
        }
        save_json(root / "setup.json", config)
        print(json.dumps(config, indent=2))
    elif args.command == "capture":
        capture(root, args)
    elif args.command == "fit":
        fit(root, args.radial)
    else:
        summarize(root)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, cv2.error) as exc:
        raise SystemExit(str(exc)) from exc
