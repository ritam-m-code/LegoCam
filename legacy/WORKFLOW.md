# Final rig measurement workflow

Use legocam.py for the session-based length and width workflow. mvp.py remains available for the earlier one-block demo.

After setup, launch the desktop controls with `.\.venv\Scripts\python app.py`. Choose a reference ID and calibration/validation role, capture it, fit calibration, capture bricks, and calculate results. The CLI below provides the same operations and is useful for repeatable collection. Run from the project folder.

## Setup

Lock the mount and focus; use the final enclosure and lighting. First obtain a saved image with the panel visible. Select a fixed measurement area entirely within the lit panel, excluding panel controls and dark borders. Leave space for the 100 mm block and assemblies. Use a new session directory after any geometry change.

```powershell
.\.venv\Scripts\python legocam.py setup setup_bright_check.png
```

Draw the measurement area and press Enter. The default camera is index 1 with MSMF, 3840 × 3032 if the setup image has that resolution, requested exposure -4 and gain 32. Camera settings are reapplied after starting the stream on every capture. The driver may acknowledge settings yet return inconsistent values; control requests and readbacks are logged. Confirm brightness/focus in the saved outlines. Opening another camera app may change controls.

## Collect calibration data

Place one artifact at a time in the central measurement area. Each capture stores five frames from one placement. Do not count those frames as five independent replacements.

```powershell
.\.venv\Scripts\python legocam.py capture --role calibration --block B100 --label B100_centre_1
```

Use B100, B080, B060, B040 and B020 for fitting; keep B090, B070, B050, B030 and B015 out of fitting. Repeat fitting captures after removing/replacing each block where time permits. Include a short block rotated near vertical if it fits the panel, to check axis consistency. The program detects the largest dark connected part and rejects significant separate objects. Inspect every overlay; labels and reference IDs must match the physical artifact.

```powershell
.\.venv\Scripts\python legocam.py fit
```

The fitted planar metric uses two positive parameters, horizontal and vertical millimetres per pixel. Only long reference dimensions are fitted, because the nearly square reference cross-sections can be confused when a block is placed on a different face. Capture B040 vertically as well as horizontal references; the fitter rejects poorly conditioned sets. For both directions, use additional short reference lengths and independent validation where possible. Dimensions are norms of the rectangle edge vectors after scaling. No offset, radial distortion or height compensation is fitted. Systematic threshold/shape bias remains observable in validation residuals. The model is appropriate only where position/orientation/size validation supports it.

Optionally run `legocam.py fit --radial` to fit one radial coefficient in addition to the two scales. Baseline and radial models are saved separately; calibration.json holds the currently selected fit. The correction maps q to q*(1+k*||q/max(image_size)||^2), with q relative to the fixed image centre, applied to midpoints of opposite rectangle sides. This is an approximate planar correction, not full camera intrinsic calibration. No additive edge offset or height correction is included. Compare separate validation captures before accepting it. Do not select a model solely on training residuals, and do not call the validation set fully independent once it has been used to select a model; use a final untouched check if possible.

## Validate

```powershell
.\.venv\Scripts\python legocam.py capture --role validation --block B050 --label B050_check_1
```

Capture each held-out block, then repeat one medium block after removal/replacement at least five times. Add modest offsets within the allowed area and a near-vertical short block. Record positions/orientations with `--placement`, e.g. `centre-vertical`, `left-horizontal`. Repeat across the intended operating area; avoid extending conclusions to untested positions. Length references span about 15–100 mm, but widths are about 10 mm: validate the expected LEGO width using the calipers too. A width prediction at 16 mm is not independently validated by 10 mm reference widths alone.

## Measure bricks

```powershell
.\.venv\Scripts\python legocam.py capture --role measurement --label lego_one_1
.\.venv\Scripts\python legocam.py results
```

Repeat for one, two and three bricks, studs up, overall outside dimensions including seams. Keep parts fully within the fixed area. The results command writes results.csv, summary.json and results.md in the session directory, with mean dimensions, fixed-placement frame standard deviations, reference errors and validation summaries. It never calls frame noise or validation RMSE a total expanded uncertainty.

## Uncertainty and report

Keep the raw caliper readings. The supplied table currently has one recorded dimension per block, without a certificate or repeated-reading uncertainty. A complete uncertainty budget requires reference calibration and contact/shape effects, scale fitting, single-frame/mean repeatability as appropriate, repositioning, spatial effects, height mismatch and drift. Shared reference systematics do not shrink with sample count. Consecutive frames may be correlated.

Use validation residuals to decide the accepted region and whether distortion correction is necessary. If time does not permit characterizing a contribution, identify it as unresolved in the report instead of substituting zero. The software is functional without claiming metrological validation that has not been performed.
