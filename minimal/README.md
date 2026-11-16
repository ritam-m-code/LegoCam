# LegoCam, minimal

Scale the camera with gauge blocks, put a LEGO piece under it, read the size off
the screen. That is the whole scope.

This is a standalone rewrite of the parent project. It does not import from it and
it does not write into it. The parent keeps the parts this one drops: HTML reports,
CSV exports, held-out validation passes, radial distortion fitting, caliper
cross-checks, setup fingerprinting and session provenance.

## Running it

```powershell
python measure.py setup        # once per physical rig
python measure.py calibrate    # once per rig, six gauge blocks
python measure.py measure      # as often as you like
```

**[RUNNING.md](RUNNING.md) is the one to read at the rig** — first run step by step,
what to do on later runs, and what each error message means. The rest of this file is
about how the code works.

`setup` opens the camera and asks you to drag a box around the area parts will sit
in. `calibrate` walks you through six blocks and works out millimetres per pixel.
`measure` shows the size of whatever is under the camera, live.

In the live window: **SPACE** captures, **Q** or **Esc** quits.

Both files it writes land in `session/`. Nothing else is written anywhere.

## The files

| File | What it does | Lines | Code |
|---|---|---:|---:|
| `scale.py` | Millimetres per pixel: fitting it, and applying it | 118 | 50 |
| `silhouette.py` | Image in, part outline out | 108 | 58 |
| `camera.py` | Newest frame, fixed exposure | 92 | 59 |
| `display.py` | The live window. Affects nothing measured | 87 | 63 |
| `measure.py` | The three commands and the live loop | 345 | 224 |
| `blocks.csv` | Caliper dimensions of the gauge blocks | 11 | — |
| **Total** | | **750** | **454** |

The second column is lines that are neither blank nor prose. Roughly a third of
this folder is explanation, which is deliberate.

Start with `scale.py`. Its module docstring explains the one piece of real maths
in the project, and `fit` is about fifteen lines of actual work.

## How the calibration works

A gauge block of known length `L` lying in view shows up as a pixel vector
`(dx, dy)` along its long side. Scaling by the two unknowns gives `(dx·sx, dy·sy)`,
and that has to come out as `L`:

```
(dx·sx)² + (dy·sy)² = L²
```

which is linear in `sx²` and `sy²`. Six blocks give six equations, solved together
by least squares. There is no iteration and no optimiser.

A block lying left-to-right has `dy ≈ 0`, so it says nothing at all about `sy`.
That is why the sequence asks for two blocks standing top-to-bottom. Skip them and
`scale.fit` refuses rather than returning a number that looks fine and is not.

## What it does not do

- **No lens distortion correction.** Parts measured near the edge of the frame will
  read differently from parts in the middle. Keep things on the crosshair. The
  parent project fits a radial term and can tell you whether it helps.
- **No uncertainty figure.** `calibrate` prints how far each gauge block landed from
  its known length, which tells you whether the fit is sane. It is not an accuracy
  claim, and it says nothing about parts it has never seen.
- **No height compensation.** The scale is fitted at gauge block height, roughly
  9.6 mm. A much taller part sits closer to the camera and reads large.
- **Nothing is logged.** Measurements print to the terminal and vanish when you
  close it.

If you need any of those, the parent project is still there and still works.

## Requirements

`numpy` and `opencv-python`, as listed in the parent `requirements.txt`.
