# Backlit brick measurement — initial prototype

Windows USB camera; fixed downward mount within a 300 mm enclosure; stock manual-focus lens; studs up; overall outside length including seams. This prototype needs real-image validation before dimensional results can be accepted.

## Reference artifacts

The supplied screenshot lists nominal printed STL artifacts: 15, 20, 30, 40, 50, 60, 70, 80, 90, 100 mm long, each 10 mm wide and 9.6 mm tall. These are not evidence of certified gauge blocks. Never enter CAD dimensions as measured reference values. Record actual lengths, heights, measurement method, temperature, repeatability, and reference uncertainty. Certified gauge blocks remain the preferred required reference for a traceable claim. Caliper-characterized prints can support a provisional demonstration; a traceable claim requires a documented calibration chain and uncertainty.

Mitutoyo lists the 500-196-30 with 0.01 mm resolution and ±0.02 mm accuracy. Resolution is not accuracy, and the specification is not a calibration certificate for your instrument. Source: https://dev.pim.mitutoyo.com/products/small-tool-instruments-and-data-management/calipers/digimatic-calipers/absolute-digimatic-caliper/

## Setup and commands

Use a Python version supported by NumPy and OpenCV wheels (Python 3.12 is a practical starting point).

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python measure.py capture reference15.png
.\.venv\Scripts\python measure.py inspect reference15.png --roi 500 1400 3000 20
.\.venv\Scripts\python measure.py calibrate references.csv --roi 500 1400 3000 20 --output calibration.json
.\.venv\Scripts\python measure.py measure brick.png --roi 500 1400 3000 20 --calibration calibration.json
```

The ROI numbers are examples only: choose them from your actual full-resolution image. Orient the long axis horizontally and select a narrow horizontal band through the body with both end boundaries visible, bright margins, and no studs or other objects. Use the identical band and placement for every capture. Tilt introduces projection error: the prototype does not correct rotation or lens distortion. Gaps crossing the selected band are rejected. It measures median row span using Otsu segmentation and linearly interpolated threshold crossings. This is a starting estimator, not yet a validated subpixel algorithm. Row scatter is a diagnostic, not independent measurement uncertainty.

Create references.csv with columns `image,actual_length_mm`; image paths are relative to that CSV. Enter only actual measured lengths. Include repeated placements across the full range; at least four captures are required. No reference lengths are prefilled to avoid accidental nominal calibration. The affine model reports its intercept and residuals and rejects extrapolation. Inspect residuals versus length and position before accepting the model. A single linear fit cannot remove field distortion.

Capture saves PNG and reports actual resolution because the USB driver may ignore requested dimensions. PNG preserves the delivered frame but cannot undo camera compression or processing. Set exposure, gain, white balance and any sharpening/noise processing manually in the vendor controls; this capture utility does not lock them. Verify settings and dimensions, stabilize illumination, focus at the part-edge height, and do not refocus or move anything after calibration. The camera is not accessed automatically.

## Calibration and validation procedure

1. Record camera/lens identity, settings, actual frame dimensions, mount distance reference, ROI, lighting warmup, ambient temperature and focus. Check clipping and blur in saved images. Determine actual field of view with a reference; do not infer it from an assumed focal length.
2. Clean and characterize references. For each printed artifact, take at least five gentle caliper readings at different contact positions; record raw readings, mean, spread, height and taper/warpage. Check caliper zero before and after. Preserve block IDs. Printed surface shape may make optical and contact lengths differ.
3. Use the same centered horizontal placement for reference and target. Capture repeated removals/replacements at each reference length, then fit. Save images, manifest and model together. Check whether residuals vary systematically with length. A large intercept is a diagnostic requiring investigation.
4. Reserve independent reference captures/lengths for validation. Do not judge performance only on fitted data. Repeat at allowed lateral positions and angles. If position effects matter, constrain placement or implement and validate geometric distortion correction before extending the usable area.
5. Measure actual brick body and reference heights. Verify the visible outline: studs may affect it depending on field position and perspective. Compare references at two or more measured support heights, using multiple lengths and repeated placements. Estimate height sensitivity experimentally. The current code does not apply a height correction. Match heights or resolve that correction before accepting results.
6. For each one-, two-, and three-brick assembly, acquire at least 20 fixed-placement frames and 10 independent replacements. Keep these datasets separate: frame noise and placement variation answer different questions. Check seam alignment and tilt.
7. Compare optical results with repeated caliper readings of the same overall dimension using gentle consistent force. If that caliper established reference lengths, agreement is a consistency check with shared systematic error, not independent proof of accuracy.

## Uncertainty and report plan

Report the measured definition, setup, reference provenance, model, calibration residual plots, held-out errors, repeatability, placement dependence, height sensitivity, limitations and raw-data locations. No achieved uncertainty can be stated before these measurements exist.

Build a standard-uncertainty budget in mm for reference calibration, reference reading/contact/shape effects, scale fit (including correlations), measurement repeatability, placement/distortion, height mismatch and drift. A rectangular bounded error ±a gives a/sqrt(3); a quantization step q gives q/sqrt(12). Use those distributions only when justified. Avoid counting a specification and its included resolution contribution twice. Reference systematic errors shared across blocks do not decrease merely because more blocks were fitted.

For a single future measurement use single-measurement repeatability. For an average of n independent readings its random contribution can be s/sqrt(n); drift and shared systematic effects do not shrink that way. Height uncertainty contributes approximately abs(dL/dh)*u(h), with sensitivity measured in this rig. Incorporate validation bias by correction plus correction uncertainty, or a justified residual allowance; do not silently ignore it or count it twice.

Combine independent standard contributions by root sum of squares; include covariance for correlated terms. State coverage factor and justification when reporting expanded uncertainty U=k*u_c (k≈2 only when justified). Report length and U to consistent precision. The software deliberately supplies no automatic U until a supported budget exists.

## Current limitations

No camera data have been analyzed. This first version has no distortion map, rotated-part estimator, automatic camera-control verification, height compensation, complete uncertainty propagation, or graphical interface. These should be driven by actual captures and measured validation errors rather than assumed accuracy targets.
