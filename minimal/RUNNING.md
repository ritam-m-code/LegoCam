# Running it

Practical notes for the rig. For what the code does and why, see [README.md](README.md).

All commands run from inside the `minimal` folder:

```powershell
cd c:\Users\ritam\OneDrive\Desktop\projects\LegoCam\minimal
```

---

## Before you touch anything

- USB camera plugged in, backlight on.
- **Close every other app that can see the camera.** Windows Camera, Teams, Zoom, OBS.
  The driver hands the camera to whoever asks first and quietly gives everyone else a
  worse one, or nothing.
- Focus set to manual and left alone. If focus changes, the scale is wrong.

---

## First run

Three commands, in order. Takes about five minutes.

### 1. `python measure.py setup`

Opens the camera and shows you one frame. Drag a box around the area where parts will
sit, then press **Enter**.

Make the box comfortably bigger than your longest gauge block — B100 is 100 mm, which
is around 1030 pixels across on this rig — and leave bright margin on all four sides.
A part touching the edge of the box measures short, and the code refuses rather than
guessing.

Writes `session/setup.json` and `session/setup_image.png`.

> If it prints `Note: asked for 3840x3032, got ...`, the camera fell back to a lower
> mode. Usually something else still had it open. Close that and run
> `python measure.py setup --replace`.

### 2. `python measure.py calibrate`

Six gauge blocks, one at a time. The banner tells you which block and which way round.
Place it, take your hands out of shot, press **SPACE**.

| Step | Block | Lay it |
|---:|---|---|
| 1 | B100 | left-to-right |
| 2 | B080 | left-to-right |
| 3 | B060 | left-to-right |
| 4 | B040 | left-to-right |
| 5 | **B040 again** | top-to-bottom |
| 6 | B020 | top-to-bottom |

Two things that matter and that the code cannot check for you:

- **"Top-to-bottom" means rotated 90° in the picture, still lying flat.** Not stood up
  on its end. Same face down for all six blocks, every time. The scale is fitted at
  that one height, so a block sitting on a different face sits closer to the lens and
  poisons the fit.
- **Centre each block on the yellow cross.** There is no lens distortion correction
  here, so position genuinely changes the answer.

Steps 5 and 6 are not optional padding. A block lying left-to-right tells the fit
nothing about the vertical scale. Without them `scale.fit` refuses outright rather
than returning a plausible wrong number.

When it finishes it prints:

```
Horizontal scale: 0.097252 mm per pixel
Vertical scale:   0.097858 mm per pixel
Largest gap between a fitted block and its known length: 0.104 mm
```

**Check that last line.** Under about 0.15 mm is healthy. Much above that and a block
was mislabelled, placed off-centre, or sitting on the wrong face — run `calibrate`
again. Over 0.5 mm it tells you so itself.

Writes `session/scale.json`.

### 3. `python measure.py measure`

Put a piece under the camera. Size appears live in the banner.

---

## Every time after

Just the last one:

```powershell
python measure.py measure
```

`setup` and `calibrate` are once per physical rig, not once per session. As long as
nothing moved, the saved scale stays good across reboots.

---

## Keys in the live window

| Key | Does |
|---|---|
| **SPACE** | Capture. Five frames averaged. In `calibrate` this records the block; in `measure` it prints a steadier number to the terminal |
| **Q** or **Esc** | Quit |

The live readout updates continuously and is fine for eyeballing. Use SPACE when you
want the number to settle — it averages five frames and rejects the capture if
anything moved.

`calibrate` remembers nothing if you quit partway through. Start it again from block 1.

---

## When you must redo setup and calibrate

Any of these invalidates the saved scale:

- The camera moved, got bumped, or was remounted.
- Focus or zoom changed.
- The working distance changed — camera raised or lowered, different table.
- The camera is now delivering a different resolution.

Lighting changes and exposure changes do not strictly need a recalibration, but they
change where the threshold falls between part and background, so re-run `calibrate`
and check the gap figure anyway.

To start over:

```powershell
python measure.py setup --replace
python measure.py calibrate
```

---

## When something goes wrong

| Message | What it means |
|---|---|
| `Cannot open the camera. Close any other app using it.` | Something else has the device. If the index itself changed, redo setup with `python measure.py setup --replace --camera 0` (`--camera` only exists on `setup`; the other commands read it from `session/setup.json`) |
| `Timed out waiting for the first camera frame.` | Camera opened but delivered nothing. Unplug and replug |
| `The camera is delivering 1920x1080, but this session was set up at 3840x3032` | Driver fell back to a lower mode. Close other camera apps and restart |
| `Camera frame is stale. Wait a moment.` | Frames stopped arriving. Usually resolves itself; if not, restart |
| `No part found. Check the backlight and the measurement region.` | Nothing dark in the box, or the backlight is off |
| `Not enough contrast between the part and the backlight.` | Backlight too dim, or exposure drifted. A white LEGO piece on a bright background will do this too |
| `More than one part in the region. Measure one at a time.` | Two pieces in the box, or a shadow reading as a second object |
| `The part touches the edge of the region. Leave a bright margin.` | Piece is bigger than the box, or pushed against its edge. Move the piece, or redo `setup` with a larger box |
| `The part moved during capture. Keep hands clear and try again.` | Hand still in shot, or the piece was nudged. Also fires on a piece that rotated |
| `Turn it so the long side runs left-to-right.` | Block is the wrong way round for this calibration step |
| `These captures only constrain one direction.` | Every block was laid the same way. Steps 5 and 6 need to be top-to-bottom |
| `setup.json is missing. Run 'python measure.py setup' first.` | Running the commands out of order |

---

## Where things live

```
minimal/
  session/
    setup.json        camera settings and the measurement box
    scale.json        mm per pixel, and how far each block landed from its known size
    setup_image.png   the frame you drew the box on
```

Measurements are not saved. They print to the terminal and go when you close it. If you
need them recorded, that is what the parent project does.

`session/` is git-ignored, so none of this gets committed.
