"""Interactive nominal-reference demo. No validated accuracy or uncertainty."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

STATUS = "PROVISIONAL: height, distortion and uncertainty unvalidated"


def outline(image, roi):
    x, y, w, h = roi
    if min(w, h) < 5 or min(x, y) < 0 or x+w > image.shape[1] or y+h > image.shape[0]:
        raise ValueError("Select a rectangle around the whole part, with bright margins")
    gray = cv2.cvtColor(image[y:y+h, x:x+w], cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    if not contours or cv2.contourArea(contours[0]) < 25:
        raise ValueError("No usable dark part found")
    if len(contours) > 1 and cv2.contourArea(contours[1]) > 0.1*cv2.contourArea(contours[0]):
        raise ValueError("Multiple parts found; tighten selection or join the assembly")
    contour = contours[0]
    bx, by, bw, bh = cv2.boundingRect(contour)
    if bx <= 1 or by <= 1 or bx+bw >= w-1 or by+bh >= h-1:
        raise ValueError("Part touches selection boundary; leave bright margins")
    contour = contour + np.array([[[x, y]]])
    rect = cv2.minAreaRect(contour)
    length, width = sorted(rect[1], reverse=True)
    if width <= 0:
        raise ValueError("Degenerate part outline")
    return float(length), float(width), cv2.boxPoints(rect).astype(np.int32)


def select(image):
    scale = min(1, 1200/image.shape[1], 800/image.shape[0])
    preview = cv2.resize(image, None, fx=scale, fy=scale)
    print("Drag around ONE whole part with bright margins. Enter confirms; C cancels.", flush=True)
    try:
        roi = cv2.selectROI("Select part - Enter confirms", preview, fromCenter=False)
    finally:
        cv2.destroyAllWindows()
    if not roi[2] or not roi[3]:
        raise ValueError("Selection cancelled")
    sx, sy = image.shape[1]/preview.shape[1], image.shape[0]/preview.shape[0]
    return [round(roi[0]*sx), round(roi[1]*sy), round(roi[2]*sx), round(roi[3]*sy)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["calibrate", "measure"])
    parser.add_argument("image")
    parser.add_argument("--length", type=float, default=100, help="Nominal reference length in mm")
    parser.add_argument("--reference-measured", action="store_true",
                        help="Record that --length is a caliper measurement rather than nominal")
    parser.add_argument("--reference-width", type=float,
                        help="Reference width in mm for a scale consistency check")
    parser.add_argument("--model", default="demo_calibration.json")
    parser.add_argument("--roi", nargs=4, type=int, help="Optional full-resolution X Y W H")
    args = parser.parse_args()
    image = cv2.imread(args.image)
    if image is None:
        raise ValueError("Cannot read image")
    roi = args.roi or select(image)
    pixels, width_pixels, box = outline(image, roi)
    size = [image.shape[1], image.shape[0]]
    result = {"status": STATUS, "image": str(Path(args.image).resolve()),
              "image_size": size, "roi": roi, "length_px": pixels, "width_px": width_pixels,
              "schema_version": 2,
              "estimator": "Otsu silhouette, rotated minimum-area rectangle"}
    if args.mode == "calibrate":
        if not np.isfinite(args.length) or args.length <= 0:
            raise ValueError("Reference length must be positive and finite")
        result.update(nominal_reference_mm=args.length, mm_per_px=args.length/pixels)
        result["reference_basis"] = "caliper measured" if args.reference_measured else "nominal"
        result["reference_length_mm"] = args.length
        # Retain the old nominal key only for genuinely nominal references.
        if args.reference_measured:
            del result["nominal_reference_mm"]
        if args.reference_width is not None:
            if not np.isfinite(args.reference_width) or not 0 < args.reference_width <= args.length:
                raise ValueError("Reference width must be positive and no greater than length")
            result["reference_width_mm"] = args.reference_width
            result["width_check_error_mm"] = width_pixels*result["mm_per_px"]-args.reference_width
            print(f"Reference width check error: {result['width_check_error_mm']:+.3f} mm")
        Path(args.model).write_text(json.dumps(result, indent=2), encoding="utf-8")
        label = f"{result['reference_basis'].upper()} {args.length:g} mm reference"
    else:
        model = json.loads(Path(args.model).read_text(encoding="utf-8"))
        if model.get("schema_version") != 2 or model["image_size"] != size:
            raise ValueError("Old/incompatible model or image resolution; redo calibration at current camera height")
        result["length_mm"] = pixels*model["mm_per_px"]
        result["width_mm"] = width_pixels*model["mm_per_px"]
        result["reference_basis"] = model["reference_basis"]
        result["calibration"] = str(Path(args.model).resolve())
        label = f"L {result['length_mm']:.1f} x W {result['width_mm']:.1f} mm - provisional"
    cv2.drawContours(image, [box], 0, (0, 255, 0), 3)
    cv2.putText(image, label, (20, 60), cv2.FONT_HERSHEY_SIMPLEX,
                1, (0, 0, 255), 2, cv2.LINE_AA)
    source = Path(args.image)
    output = source.with_name(source.stem + f"_{args.mode}_overlay.png")
    if not cv2.imwrite(str(output), image):
        raise ValueError("Could not save overlay")
    source.with_name(source.stem + f"_{args.mode}_result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    print(label)
    print(f"Overlay: {output}")
    print(STATUS)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, cv2.error) as exc:
        raise SystemExit(str(exc)) from exc
