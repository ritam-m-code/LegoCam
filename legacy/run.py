"""Command-line entry point for the LegoCam experiment. Run --help for commands."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import time

import cv2
import numpy as np

import calibrate
from camera import Camera
from legocam import (
    dimensions,
    fit,
    read_json,
    records,
    save_json,
    setup_hash,
    summarize,
    validation_checks,
)
from vision import select

PROJECT = Path(__file__).resolve().parent
DEFAULT_SESSION = "sessions/reused"


def setup_session(root, args):
    """Save camera settings and a user-selected lit region for a new physical rig."""
    if (root / "setup.json").exists():
        raise ValueError("Session already exists. Choose a new --session after changing the rig.")
    config = {
        "camera": args.camera,
        "backend": "msmf",
        "width": args.width,
        "height": args.height,
        "exposure": args.exposure,
        "gain": args.gain,
        "focus": "manual fixed",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "placement_policy": "image-centre crosshair",
    }
    print("Opening camera. Close Camera Settings and other camera apps first.", flush=True)
    camera = Camera(config)
    try:
        deadline = time.monotonic() + 60
        while camera.snapshot() is None:
            if camera.error:
                raise ValueError(camera.error)
            if time.monotonic() > deadline:
                raise ValueError("Timed out waiting for the camera")
            time.sleep(0.1)
        frame = camera.snapshot()[2].copy()
    finally:
        camera.stop.set()
        camera.thread.join(timeout=5)
    config["roi"] = select(frame)
    root.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(root / "setup_image.png"), frame):
        raise ValueError("Could not save setup image")
    save_json(root / "setup.json", config)
    print(f"Setup saved in {root}. Keep the camera, focus and lighting fixed.")


def compare_models(root):
    """Compare long-dimension check errors; retain both models for inspection."""
    check_records, check_scope = validation_checks(root, records(root))
    if len({r["block"] for r in check_records}) < 2:
        raise ValueError("Capture at least two different held-out blocks before comparing models")
    comparisons = {}
    models = {}
    for name, radial in (("baseline", False), ("radial", True)):
        fit(root, radial=radial, verbose=False)
        model = read_json(root / "calibration.json")
        models[name] = model
        errors = [
            float(
                np.mean(
                    [
                        dimensions(o, model["scales_mm_per_px"], model["radial_k"])[0]
                        for o in record["observations"]
                    ]
                )
            )
            - record["reference"]["length_mm"]
            for record in check_records
            if record["setup_hash"] == model["setup_hash"]
        ]
        if not errors:
            raise ValueError("No validation captures match the current setup")
        comparisons[name] = {
            "length_errors_mm": errors,
            "length_rmse_mm": float(np.sqrt(np.mean(np.square(errors)))),
        }
    selected = min(comparisons, key=lambda name: comparisons[name]["length_rmse_mm"])
    save_json(root / "calibration.json", models[selected])
    save_json(
        root / "model_comparison.json",
        {
            "models": comparisons,
            "selected": selected,
            "check_scope": check_scope,
            "selection_basis": "Smallest long-dimension check RMSE; short reference sides are not fitted",
            "limitation": "Checks used for model selection are no longer an untouched final test. Check actual bricks next.",
        },
    )
    summarize(root, verbose=False)
    print(f"Selected {selected}. Check results on actual LEGO bricks before claiming accuracy.")


def record_comparison(root, args):
    """Attach a caliper reading to one capture, preserving earlier readings."""
    if not all(np.isfinite(value) and value > 0 for value in (args.length, args.width)):
        raise ValueError("Caliper dimensions must be positive finite numbers")
    measurements = [r for r in records(root) if r["role"] == "measurement"]
    if args.capture:
        measurements = [
            r for r in measurements if r["id"] == args.capture or r["label"] == args.capture
        ]
    if not measurements:
        raise ValueError("No matching brick capture. Save a measurement with Space first.")
    record = measurements[-1]
    path = root / "comparisons" / (record["id"] + ".json")
    history = []
    if path.exists():
        previous = read_json(path)
        history = previous.pop("previous_readings", []) + [previous]
    save_json(
        path,
        {
            "record_id": record["id"],
            "label": record["label"],
            "caliper_length_mm": args.length,
            "caliper_width_mm": args.width,
            "recorded_utc": datetime.now(timezone.utc).isoformat(),
            "source": "User supplied caliper readings",
            "previous_readings": history,
        },
    )
    summarize(root, verbose=False)
    summary = read_json(root / "summary.json")
    print(next(row for row in summary["records"] if row["id"] == record["id"]))


def show_results(summary):
    """Give the presenter a small table instead of a dump of capture metadata."""
    print(f"{'Capture':28} {'Role':12} {'Length mm':>10} {'Width mm':>10}")
    for row in summary["records"]:
        if row["role"] == "diagnostic":
            continue
        print(
            f"{row['label']:28} {row['role']:12} {row['length_mm']:10.3f} {row['width_mm']:10.3f}"
        )
        if row.get("caliper_length_mm") is not None:
            print(
                f"  Camera minus calipers: length {row['caliper_length_error_mm']:+.3f} mm; width {row['caliper_width_error_mm']:+.3f} mm"
            )
    stats = summary["length_validation"]
    if stats:
        print(
            f"Reference-check length RMSE: {stats['rmse_mm']:.3f} mm. This is not total uncertainty."
        )
    print(summary["uncertainty_status"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("setup", "Configure a new physical rig and select its lit measurement area"),
        ("calibrate", "Run or resume the full guided reference sequence"),
        ("validate", "Run a fresh B030 horizontal/vertical and B050 horizontal check"),
        ("align", "Show the live crosshair without recording"),
        ("measure", "Show live length/width; Space saves a five-frame measurement"),
        ("models", "Compare baseline and radial models using reference checks"),
        ("results", "Recalculate saved results without accessing the camera"),
        ("example", "Show the recorded experiment snapshot without a camera or local session"),
        ("compare", "Record caliper dimensions for a saved brick capture"),
        ("report", "Rebuild the printable HTML report"),
        ("package", "Zip source and results; optionally include raw images"),
    ):
        command_parser = sub.add_parser(command, help=help_text)
        command_parser.add_argument("--session", default=DEFAULT_SESSION)
        if command == "setup":
            command_parser.add_argument("--camera", type=int, default=1)
            command_parser.add_argument("--width", type=int, default=3840)
            command_parser.add_argument("--height", type=int, default=3032)
            command_parser.add_argument("--exposure", type=float, default=-4)
            command_parser.add_argument("--gain", type=float, default=32)
        if command == "compare":
            command_parser.add_argument("--length", type=float, required=True)
            command_parser.add_argument("--width", type=float, required=True)
            command_parser.add_argument(
                "--capture", help="Capture ID or label; otherwise use latest brick capture"
            )
        if command == "package":
            command_parser.add_argument("--include-images", action="store_true")
    args = parser.parse_args(argv)
    # All relative paths use the repository, including when launched by a shortcut.
    os.chdir(PROJECT)
    root = Path(args.session)
    if args.command == "example":
        print("RECORDED EXAMPLE - not a live measurement")
        show_results(read_json(PROJECT / "examples" / "current_rig" / "summary.json"))
    elif args.command == "setup":
        setup_session(root, args)
    elif args.command in ("calibrate", "validate", "align", "measure"):
        if not (root / "setup.json").exists():
            raise ValueError(
                "No session setup. Run 'python run.py setup --session sessions/NAME' first."
            )
        live_args = ["--session", str(root)]
        if args.command == "validate":
            progress = "checks_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + ".json"
            live_args += ["--plan", "quick_validation.json", "--progress-file", progress]
            print("To resume this particular check pass after quitting:")
            print(".\\.venv\\Scripts\\python calibrate.py " + " ".join(live_args), flush=True)
        elif args.command == "align":
            live_args += ["--align-only"]
        elif args.command == "measure":
            live_args += ["--measure"]
        calibrate.main(live_args)
    elif args.command == "models":
        compare_models(root)
    elif args.command == "compare":
        record_comparison(root, args)
    elif args.command == "package":
        from package_project import package

        package(root, include_images=args.include_images)
    else:
        summary = summarize(root, verbose=False)
        show_results(summary)
        if args.command == "report":
            from build_report import build

            build(root, Path("deliverables/LegoCam_report.html"))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, cv2.error) as error:
        raise SystemExit(str(error)) from error
