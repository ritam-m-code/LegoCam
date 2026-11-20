# LegoCam

Measure the outside length and width of LEGO bricks from a backlit overhead USB camera image. Camera, focus and lighting stay fixed between calibration and measurement. Height is not measured.

## Start here

On the current laptop, open PowerShell in this folder and run:

```powershell
.\.venv\Scripts\python run.py measure
```

This uses the existing `sessions/reused` calibration. Centre the brick on the yellow cross, studs up. A green outline means the placement checks passed. Remove your hands and press **Space** to save five frames. **Q** closes the view. **R** clears a failed capture so you can retry.

The live estimate is provisional. The first brick measured 31.579 × 15.754 mm optically versus the corrected caliper reading of 31.80 × 15.79 mm: differences of −0.221 and −0.036 mm. Reference-check length RMSE was 0.082 mm across three model-selection checks. That is not a total uncertainty estimate.

Read [PRESENTATION.md](PRESENTATION.md) for the demonstration procedure and troubleshooting, and [CODE_GUIDE.md](CODE_GUIDE.md) to understand the implementation.

## Install on another computer

Use Windows and a Python version supported by NumPy/OpenCV. This project was exercised with Python 3.14.3. A repository clone contains code and reference dimensions, not your local camera session or images.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python run.py --help
```

Transfer a full session backup from this laptop, or configure and calibrate the new rig:

```powershell
.\.venv\Scripts\python run.py setup --session sessions/new_rig --camera 1
.\.venv\Scripts\python run.py calibrate --session sessions/new_rig
.\.venv\Scripts\python run.py models --session sessions/new_rig
.\.venv\Scripts\python run.py measure --session sessions/new_rig
```

During setup, select the lit measurement area, excluding panel controls and dark borders. Our camera delivers 3840 × 3032. For another supported resolution, pass `--width` and `--height` to setup. Camera index 1 is specific to this laptop.

## Commands

Every command accepts `--session PATH`. The default is our local `sessions/reused` experiment.

| Command | Purpose |
|---|---|
| `setup` | Create camera settings and select the lit measurement region |
| `calibrate` | Guide reference placements and save/resume progress |
| `validate` | Collect a fresh three-placement check without replacing the selected model |
| `align` | Show the camera and crosshair without recording |
| `measure` | Show live dimensions; Space saves a measurement |
| `models` | Compare baseline/radial candidates using long-dimension check errors |
| `results` | Recalculate saved dimensions and errors without opening the camera |
| `example` | Show the recorded numerical snapshot without camera access |
| `compare --length 31.80 --width 15.79` | Attach caliper readings to the latest brick capture |
| `report` | Rebuild `deliverables/LegoCam_report.html` |
| `package --include-images` | ZIP source, results and raw frames for backup/transfer |

`compare --capture ID` selects a particular capture. Corrected caliper entries retain the earlier readings. Use the actual part's caliper dimensions, not nominal LEGO dimensions.

## Code map

| File | Responsibility |
|---|---|
| `run.py` | Commands for the experiment and presentation |
| `camera.py` | USB capture on a worker thread |
| `vision.py` | Thresholding, contour and rectangle detection |
| `calibrate.py` | Live overlay, placement checks and guided collection |
| `legocam.py` | Session records, scale fitting, correction and results |
| `build_report.py` | Printable HTML report |
| `reference_blocks.csv` | Supplied caliper dimensions of the ten references |
| `quick_validation.json` | B030 horizontal/vertical and B050 horizontal check |
| `legacy/` | Earlier prototypes; not the presentation workflow |

Raw images, session data and generated reports stay local and are ignored by Git. `examples/` contains a numerical experiment snapshot for review, not a live calibration.

## Limits

The stock lens is not telecentric. Position, reference height, shadows, blur and surface shape affect the silhouette. The radial model is approximate and assumes the principal point is at the image centre. Recalibrate after changing camera geometry, focus, resolution or lighting. The printed reference artifacts have caliper measurements, not certified gauge-block traceability. Identify which reference face is down before interpreting short-side errors. Validate actual LEGO length and width separately from model selection.

## Development

Optional formatting tools are in `requirements-dev.txt`. The development checks are kept locally and are not needed for the submitted measurement pipeline. Software checks do not establish camera accuracy; use reference and actual-part comparisons for that.
