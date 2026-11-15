"""Initial horizontal silhouette measurement CLI. See README.md before use."""
import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np


BACKENDS = {"dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF, "any": cv2.CAP_ANY}


def camera_frame(index, backend, width=None, height=None):
    """Release every attempted device, including failed reads."""
    attempts = BACKENDS if backend == "auto" else [backend]
    for name in attempts:
        cap = cv2.VideoCapture(index, BACKENDS[name])
        try:
            if not cap.isOpened():
                continue
            if width is not None:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            frame = None
            for _ in range(15):
                ok, candidate = cap.read()
                if ok and candidate is not None and candidate.size:
                    frame = candidate
            if frame is not None:
                return frame, name
        finally:
            cap.release()
    raise ValueError(f"No frame from camera {index} using {backend}. Close camera apps/settings, "
                     "check Windows desktop-app camera permission, then run probe.")


def span(path, roi):
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Cannot read {path}")
    x, y, w, h = roi
    if min(x, y) < 0 or min(w, h) < 1 or x+w > image.shape[1] or y+h > image.shape[0]:
        raise ValueError("ROI outside image")
    crop = image[y:y+h, x:x+w].astype(float)
    threshold, _ = cv2.threshold(crop.astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    foreground = crop[crop <= threshold]
    background = crop[crop > threshold]
    if not foreground.size or not background.size:
        raise ValueError("No foreground/background contrast")
    threshold = (float(np.median(foreground)) + float(np.median(background))) / 2
    widths = []
    for row in crop:
        dark = np.flatnonzero(row <= threshold)
        if len(dark) < 2:
            continue
        a, b = int(dark[0]), int(dark[-1])
        if a == 0 or b == w-1:
            raise ValueError("Silhouette touches ROI boundary")
        if np.any(row[a:b+1] > threshold):
            raise ValueError("Multiple dark intervals; use a clean body-band ROI")
        left = a-1 + (row[a-1]-threshold)/(row[a-1]-row[a])
        right = b + (threshold-row[b])/(row[b+1]-row[b])
        widths.append(right-left)
    if len(widths) < max(5, h//2):
        raise ValueError("Too few usable rows")
    return {"pixels": float(np.median(widths)), "row_span_sd_px": float(np.std(widths)),
            "usable_rows": len(widths), "image_size": [image.shape[1], image.shape[0]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    capture = sub.add_parser("capture")
    capture.add_argument("output")
    capture.add_argument("--camera", type=int, default=0)
    capture.add_argument("--width", type=int, default=4056)
    capture.add_argument("--height", type=int, default=3040)
    capture.add_argument("--backend", choices=["auto", *BACKENDS], default="auto")
    probe = sub.add_parser("probe", help="Read a frame at default resolution; does not save images")
    probe.add_argument("--max-index", type=int, default=3)
    probe.add_argument("--backend", choices=["auto", *BACKENDS], default="auto")
    for name in ("inspect", "calibrate", "measure"):
        p = sub.add_parser(name)
        p.add_argument("input")
        p.add_argument("--roi", nargs=4, type=int, required=True, metavar=("X", "Y", "W", "H"))
        if name == "calibrate":
            p.add_argument("--output", default="calibration.json")
        if name == "measure":
            p.add_argument("--calibration", required=True)
    args = parser.parse_args()
    if args.command == "probe":
        for index in range(args.max_index + 1):
            try:
                frame, backend = camera_frame(index, args.backend)
                print(json.dumps({"camera": index, "backend": backend,
                                  "actual_size": [frame.shape[1], frame.shape[0]]}), flush=True)
            except ValueError as exc:
                print(str(exc), flush=True)
        return
    if args.command == "capture":
        frame, backend = camera_frame(args.camera, args.backend, args.width, args.height)
        if not cv2.imwrite(args.output, frame):
            raise ValueError("Image save failed")
        print(json.dumps({"saved": args.output, "backend": backend,
                          "actual_size": [frame.shape[1], frame.shape[0]],
                          "warning": "Verify manual camera controls before calibration"}, indent=2))
        return
    if args.command == "calibrate":
        manifest = Path(args.input)
        with manifest.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if len(rows) < 4:
            raise ValueError("Use at least four reference captures across the range")
        results = [span(manifest.parent / r["image"], args.roi) for r in rows]
        if len({tuple(r["image_size"]) for r in results}) != 1:
            raise ValueError("Image sizes differ")
        px = np.array([r["pixels"] for r in results])
        mm = np.array([float(r["actual_length_mm"]) for r in rows])
        if not np.all(np.isfinite(mm)) or np.any(mm <= 0) or np.ptp(px) < 10:
            raise ValueError("Invalid reference lengths or insufficient length range")
        slope, intercept = np.polyfit(px, mm, 1)
        if slope <= 0:
            raise ValueError("Invalid scale")
        residual = mm - (slope*px+intercept)
        model = {"mm_per_px": float(slope), "intercept_mm": float(intercept),
                 "residuals_mm": residual.tolist(), "fit_residual_sd_mm": float(np.sqrt(np.sum(residual**2)/(len(mm)-2))),
                 "range_px": [float(px.min()), float(px.max())], "roi": args.roi,
                 "image_size": results[0]["image_size"], "manifest": str(manifest.resolve()),
                 "status": "PROVISIONAL: uncertainty and spatial/height validation required"}
        Path(args.output).write_text(json.dumps(model, indent=2), encoding="utf-8")
        print(json.dumps(model, indent=2))
        return
    result = span(args.input, args.roi)
    if args.command == "measure":
        model = json.loads(Path(args.calibration).read_text(encoding="utf-8"))
        if args.roi != model["roi"] or result["image_size"] != model["image_size"]:
            raise ValueError("ROI/image size differ from calibration")
        if not model["range_px"][0] <= result["pixels"] <= model["range_px"][1]:
            raise ValueError("Outside calibrated range")
        result["length_mm"] = model["mm_per_px"]*result["pixels"]+model["intercept_mm"]
        result["status"] = model["status"]
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as exc:
        raise SystemExit(str(exc)) from exc

