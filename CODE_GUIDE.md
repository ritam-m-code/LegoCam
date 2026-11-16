# How the code works

Read these files in this order: `run.py`, `camera.py`, `vision.py`, `calibrate.py`, then `legocam.py`. `build_report.py` formats the saved results; it does not measure objects.

## The data path

```text
USB camera frame
    -> grayscale image in the selected lit region
    -> dark silhouette mask
    -> largest valid contour
    -> rotated rectangle and two edge vectors in pixels
    -> optional radial correction
    -> horizontal/vertical millimetres-per-pixel scales
    -> length and width in millimetres
    -> saved results and independent caliper comparison
```

## Camera capture

`camera.Camera` owns the USB camera. It runs in a worker thread because a high-resolution frame read can block; the main thread must still redraw the window and respond to keys. Each frame has a sequence number and timestamp, so the live code avoids counting the same frame twice and can detect stale previews.

It requests a frame size, manual exposure and gain. The Windows driver has sometimes acknowledged a setting while returning an inconsistent readback. Both requests and readbacks are saved; the program does not assert they are independently verified. Manual lens focus is a physical adjustment.

## Finding the part

`vision.outline` crops the fixed measurement region, converts to grayscale and applies a small Gaussian blur. Otsu thresholding chooses a separation between the darker part and brighter background. External contours describe connected dark regions. The largest contour is the candidate part; significant extra parts or a contour hitting the region border are rejected.

OpenCV's minimum-area rectangle gives a box that can rotate with the part. The long side is called length and the short side width. `vision.detect` returns its full-resolution edge vectors, centre, outline and simple image-quality diagnostics. The reduced image on screen is only a preview; saved pixel measurements use the original resolution. Pixel-level contour detection is not a claim of validated subpixel accuracy.

## Placement and capture

`calibrate.placement_check` compares the part centre with the image centre and, for references, checks horizontal/vertical orientation. The image centre is an approximate principal point; it has not been measured by an intrinsic camera calibration. The yellow cross gives a repeatable target. Off-centre silhouettes of tall objects can include edges at different heights, which is why alignment matters even if a distortion correction is fitted.

Space starts a short hands-clear delay, then collects five new frames. If the part leaves the accepted region, capture is cancelled. `save_batch` checks motion, saves raw images and writes one placement record. A placement record contains multiple frames; they are not treated as multiple independent replacements. Q closes the camera and leaves saved data intact.

The full plan reserves different block IDs for fitting and checking. The shorter `quick_validation.json` plan collects three checks. A check-only run preserves the selected model instead of accidentally replacing it with a new baseline fit.

## Calibration maths

`legocam.fit_metric` estimates two positive scale factors: horizontal `s_x` and vertical `s_y`, both in mm/pixel. For a pixel edge `(dx, dy)`, the physical dimension is:

```text
dimension_mm = sqrt((s_x * dx)^2 + (s_y * dy)^2)
```

Squaring that equation makes a linear least-squares fit for `s_x²` and `s_y²`. The known quantity is each reference's actual caliper length. We average squared edge components within one placement and give placements relative weighting, rather than letting the longest blocks dominate solely because their squared dimensions are larger.

Only the long reference dimension is fitted. The short sides are nearly square and can be confused if a block rests on another face. Rotating short reference blocks lets their known lengths calibrate the vertical direction too. The fit rejects data that cannot independently constrain both directions.

## Approximate radial correction

The baseline model uses only the two scales. The radial candidate first adjusts image-centred endpoint coordinates:

```text
radius_squared = (qx / max_image_dimension)^2 + (qy / max_image_dimension)^2
corrected_point = point * (1 + k * radius_squared)
```

`corrected_vectors` applies this to the midpoints of opposing rectangle sides. A bounded search finds `k`, refitting the two scales for each candidate. This is a simple empirical correction, not a full lens model or a height correction. It assumes the distortion centre is the image centre and should not be trusted outside the tested region.

`run.compare_models` evaluates both candidates on saved reference checks and selects the smaller long-dimension check RMSE. Both model files and the comparison are retained. Once checks are used to select a model, they cannot also be advertised as a completely untouched final test. Compare the actual LEGO parts afterward.

## Results and calipers

`legocam.summarize` applies the selected model to every compatible saved record. It writes mean length/width, within-placement frame standard deviations, reference errors and warnings. A configuration hash catches changes to recorded setup settings, but cannot detect an unrecorded physical movement of the lens or mount.

`run.record_comparison` attaches independently read caliper dimensions to a particular capture. Revisions retain the previous entries. The comparison always uses camera minus caliper; it never adjusts calibration to force agreement. The same caliper established the reference sizes, so some errors are shared rather than independent.

RMSE is the square root of mean squared discrepancies. It summarizes those checks. It is not a guaranteed maximum error, nor is it a total expanded uncertainty. Frame standard deviation describes noise with a fixed placement. Repositioning, drift, reference uncertainty, optical geometry and model bias need their own assessment.

## Files to inspect while explaining the experiment

Open `reference_blocks.csv` to show actual reference sizes. Open `sessions/reused/calibration.json` to show the selected coefficients. Open one JSON in `records/` to show raw observations and image links. Open `results.csv` to show comparisons. The numerical snapshot in `examples/` makes the current evidence readable on GitHub without publishing the camera photos.
