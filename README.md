# LegoCam

Measure LEGO bricks with a camera. Scale the camera against gauge blocks of known
length, put a brick under it, read the size off the screen.

## Install

```powershell
pip install -r requirements.txt
```

## Use

Three commands, in this order.

### `python measure.py setup`

Run once per physical rig. Opens the camera and asks you to drag a box around the
area parts will sit in. Records the camera index, resolution, exposure and gain so
every later run opens the camera the same way.

### `python measure.py calibrate`

Run once per rig, after setup. Walks you through six gauge blocks and works out
millimetres per pixel, horizontally and vertically.

Four of the blocks lie across the frame and two stand top to bottom. The upright
ones are what pin down the vertical scale — a block lying flat says nothing about
it. Skip them and calibration refuses rather than returning a number that looks
fine and is not.

### `python measure.py measure`

Run as often as you like. Shows the size of whatever is under the camera, live.

**SPACE** captures, **Q** or **Esc** quits.

## Notes

Both files it writes go in `session/`, which is git-ignored. Measurements print to
the terminal and are not saved.

Recalibrate if the camera moves, the focus changes, or the lighting changes. The
scale factor is stored and reused, so the geometry has to stay put between
calibrating and measuring.

[RUNNING.md](RUNNING.md) has the step-by-step for the rig and what each error
message means.

## Files

| File | What it does |
|---|---|
| `measure.py` | The three commands and the live loop |
| `scale.py` | Millimetres per pixel: fitting it, and applying it |
| `silhouette.py` | Image in, part outline out |
| `camera.py` | Newest frame, fixed exposure |
| `display.py` | The live window |
| `blocks.csv` | Caliper dimensions of the gauge blocks |

`legacy/` holds the earlier, larger version of this project: HTML reports, CSV
exports, held-out validation, radial distortion fitting and session provenance.
Nothing in the root depends on it.
