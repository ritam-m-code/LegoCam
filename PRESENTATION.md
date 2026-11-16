# Running LegoCam without an assistant

## Before the demonstration

Use the same camera mount, focus, lighting and frame size as calibration. Moving the entire closed rig to another table is different from moving the camera relative to its panel: if that relative geometry or focus changes, recalibrate. Reconnect the camera, turn on the panel, close the enclosure, and close Camera Settings, the old live window and other camera software.

In PowerShell:

```powershell
cd C:\Users\terre\OneDrive\Documents\ChatGPT\mte201
.\.venv\Scripts\python run.py results
.\.venv\Scripts\python run.py measure
```

The first command checks that the existing session and model load without needing the camera. The second opens the live view using `sessions/reused`. Do not run `setup` on the presentation session or refit it merely because you restarted the computer.

## A short demonstration

1. Explain: “The panel makes a dark silhouette. We measure its image dimensions and convert pixels into millimetres using measured reference blocks.”
2. Put one brick studs up, long side approximately horizontal. Move its midpoint onto the yellow cross. The movement text says which direction to slide it.
3. Explain: “The camera is not telecentric, so consistent placement and similar object heights matter. The green outline means our placement and detection checks passed, not that accuracy is guaranteed.”
4. Remove your hands. Press Space in the camera window. Wait until it says the measurement was saved. It stores five frames from that placement.
5. Show the live length/width. Move the brick, replace it and capture again if demonstrating repeatability. Five frames without moving a brick are different from five independent placements.
6. If demonstrating two/three-brick assemblies, centre the whole assembly on the cross and keep both ends inside the lit region. Measure the same outside span with the calipers. Include seam gaps in both methods.
7. Press Q to close the live view before running another camera command.

## Record the independent comparison

Reopen and reseat the calipers gently for repeated readings. Use body length and width, not stud diameter or a nominal value from a drawing. This records the readings against the most recent saved brick:

```powershell
.\.venv\Scripts\python run.py compare --length 31.80 --width 15.79
```

Replace the numbers with that captured part's actual readings. For an earlier capture, copy its full ID from `sessions/reused/results.csv`:

```powershell
.\.venv\Scripts\python run.py compare --capture CAPTURE_ID --length 31.80 --width 15.79
```

Earlier readings are preserved when corrected. This command calculates camera minus caliper error. It does not change calibration to force agreement.

## Show results and the report

```powershell
.\.venv\Scripts\python run.py report
Invoke-Item .\deliverables\LegoCam_report.html
```

The HTML report opens in a browser and can be printed to PDF. It is rebuilt from session data, so regenerate it after new captures or comparisons. The main numerical files are:

| File in sessions/reused | Meaning |
|---|---|
| `setup.json` | Camera controls, resolution and fixed measurement region |
| `calibration.json` | Currently selected scale/correction parameters |
| `calibration_baseline.json` / `calibration_radial.json` | Both candidate models |
| `model_comparison.json` | Candidate check errors and selection rationale |
| `records/` | One metadata record per placement; references raw frames |
| `images/` | Raw frames and overlays captured in this session |
| `comparisons/` | Caliper readings and their correction history |
| `results.csv` | Mean dimensions, frame scatter, errors and warnings |
| `summary.json` | Machine-readable results and validation statistics |

Some reused raw images live in `sessions/final_rig/images`; record paths point there. Keep that folder too.

## Check calibration without repeating everything

```powershell
.\.venv\Scripts\python run.py validate
```

Follow three live prompts: B030 horizontal, B030 vertical, B050 horizontal. Space saves each placement. This creates a new check pass and keeps the selected calibration unchanged. Q preserves its progress; the terminal prints the full direct command needed to resume that pass. Check the errors before presenting a numerical accuracy claim.

## When a full calibration is needed

After moving the camera relative to the panel, changing focus/resolution, or changing illumination conditions substantially, create a new session:

```powershell
.\.venv\Scripts\python run.py setup --session sessions/presentation_rig --camera 1
.\.venv\Scripts\python run.py calibrate --session sessions/presentation_rig
.\.venv\Scripts\python run.py models --session sessions/presentation_rig
.\.venv\Scripts\python run.py measure --session sessions/presentation_rig
```

Setup opens a saved camera frame for selecting the lit region. Draw inside the panel border, excluding its controls, with room for the longest reference. The full wizard guides 17 placements using the supplied reference dimensions. Q saves progress; run the same calibrate command to resume. The model command compares baseline and radial candidates using reference-check length errors and preserves both fits. Those checks have then been used for model selection; actual LEGO comparisons provide the next check.

Pass the same `--session` to all commands for a new experiment. The default remains the existing `sessions/reused` session unless you specify another.

## Back up before the presentation

```powershell
.\.venv\Scripts\python run.py report
.\.venv\Scripts\python run.py package --include-images
```

Copy `deliverables/LegoCam.zip` to a USB drive or another local location. Extract it and install the requirements on the other laptop. A Git clone alone does not contain the local calibration session or images. Without `--include-images`, the ZIP contains code/results but not the raw evidence. The ZIP also contains the report.

## What the current numbers mean

The three reference checks gave length RMSE 0.293 mm with the baseline and 0.082 mm with the radial model; the largest radial-model discrepancy was 0.130 mm. The first brick was 31.579 × 15.754 mm optically against updated caliper readings of 31.80 × 15.79 mm. The differences were −0.221 mm in length and −0.036 mm in width. These are observed comparisons, not a guaranteed tolerance or 95% uncertainty interval. The earlier caliper length was 31.69 mm, so reference reading variation also needs explaining.

If asked whether it achieves ±0.1 mm, answer: “This first brick's length comparison does not. The width discrepancy is smaller, but we have not established a total accuracy specification. We report the actual errors and the remaining uncertainty sources.”

## Troubleshooting

| Symptom | Action |
|---|---|
| Camera unavailable or black window | Close all camera programs, wait a few seconds, check cable/panel, restart measure |
| Wrong camera | On a new session, try `setup --camera 0` or another known device index |
| Still says opening camera | High-resolution MSMF startup can take several seconds; allow it to finish |
| Orange outline or move instructions | Centre the entire part and use the requested orientation |
| Size differs from expected block | Check the nominal block ID; Space will not advance a clearly wrong size |
| Part touches region boundary | Reposition it; if it cannot fit, the setup/measurement region needs revisiting |
| Object moved during capture | Keep hands clear and retry with R, then Space |
| No session setup | Restore the full session backup or create/calibrate a new session |
| Old calibration sequence message | Use the original plan/progress file to resume, or a new session for a new experiment |
| Numbers suddenly change | Check settings, focus, lighting, part position and geometry; run reference validation |

If the camera cannot be used, `python run.py example` displays the recorded numerical snapshot included in Git. Say clearly that these are recorded values, not a live measurement. The existing HTML report also works without the camera.

Do not guess new calibration coefficients during the presentation to make a result match a desired value. Preserve the failed check and explain what it reveals.
