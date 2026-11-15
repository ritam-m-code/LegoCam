# Nominal-reference MVP

This workflow can proceed while the caliper is unavailable. It uses nominal 100 mm as a temporary reference. Results demonstrate operation; accuracy, reference length, height mismatch and lens distortion remain unvalidated. Replace this calibration with measured references later.

1. Keep the camera mount, focus, capture settings and resolution fixed. Position the reference near the image centre, alone on the lit panel. Improve focus/exposure first if possible.
2. Calibrate from a saved image:

```powershell
.\.venv\Scripts\python mvp.py calibrate first_capture.png --length 100
```

Drag a rectangle around the entire dark 100 mm reference, including bright margins on all sides. Exclude the panel edge and other objects. Press Enter. Inspect the saved green outline: it must follow the intended part. Escape/C cancels selection. Calibration is stored separately in demo_calibration.json.

3. Replace the reference with a brick or connected assembly in the same central area, then capture:

```powershell
.\.venv\Scripts\python measure.py capture brick.png --camera 1 --backend msmf --width 3840 --height 3032
.\.venv\Scripts\python mvp.py measure brick.png
```

Select the whole assembly with bright margins and press Enter. The console reports an approximate length; an annotated PNG and JSON record are saved beside the image. Re-running overwrites those demo outputs. The reference and target must use the same resolution. Modest in-plane rotation is handled by a rotated bounding rectangle. This measures the outer silhouette including any stud projection, seams and shape defects; inspect the outline. Detached parts are rejected. Connected assemblies with small gaps can also be rejected.

The estimator works on full-resolution pixels after selection on a reduced preview. It uses a thresholded contour rather than claiming subpixel accuracy. Rounded ends, shadows, flare, blur, surface transmission and distortion can bias its result. One-point nominal calibration provides neither a validated measurement range nor a defensible uncertainty. Do not use its output as the final report's accuracy evidence.
