# Live guided calibration

Close the older LegoCam window, Camera Settings and other camera apps first. From the project folder:

```powershell
.\.venv\Scripts\python calibrate.py
```

The wizard creates a fresh session at sessions/guided, copying only camera/ROI settings from sessions/final_rig. It does not mix in the earlier off-centre calibration records. The rig, focus, backlight and settings must remain fixed. The image centre is an approximate optical-axis location, not a measured principal point.

For this project's saved captures, sessions/reused contains five selected calibration placements and three diagnostic placements copied by metadata reference, preserving all original files. The minimum independent check sequence is:

```powershell
.\.venv\Scripts\python calibrate.py --session sessions/reused --plan quick_validation.json
```

This requests B030 horizontally, B030 vertically, then B050 horizontally. It preserves progress and regenerates the baseline calibration/results/report at completion. These checks do not guarantee that no further captures are needed; their errors decide that. The retained long dimensions span the image-centre coordinate in their measurement direction; off-axis geometry and field effects still need validation. Source/reference choices are recorded in sessions/reused/reuse_audit.json.

## Controls

- Put the block named at the top of the window on the panel. H means the long side runs left-to-right; V means top-to-bottom. Keep the same face down when rotating.
- Centre its midpoint on the yellow cross. Orange outlines and movement instructions become green when placement/orientation are acceptable.
- Remove your hands and press Space while the camera window is active. After a short pause, five new frames are captured and checked for movement. The next block is displayed automatically.
- A rough size check catches clearly incorrect blocks after the first reference. It is not proof of physical block identity.
- R clears a failed-capture message so you can retry. Q or Escape closes the camera and preserves progress. Running the same command resumes the current step.

The sequence uses B100, B080, B060, B040, B020 and B015 for calibration, with short references rotated to calibrate both image directions. B090, B070, B050 and B030 are held out for validation. Three additional B030 captures ask for removal/replacement to assess placement repeatability. Use the IDs in reference_blocks.csv, based on nominal design lengths; the actual measured lengths are used for fitting.

The final step automatically fits the baseline planar metric, calculates results and writes sessions/guided/report.html. It does not automatically select the experimental radial model. No total expanded uncertainty is claimed merely because the sequence finishes. Inspect results.csv, summary.json and the report, and compare brick measurements against calipers.

## Live brick measurement

```powershell
.\.venv\Scripts\python calibrate.py --measure
```

Centre a brick or assembly on the cross. Length and width are displayed live. Space records five frames and updates session results. Replace the part, then repeat. Results are provisional outside validated size/orientation/height conditions. To rebuild the full report after measurements:

```powershell
.\.venv\Scripts\python build_report.py --session sessions/guided --output deliverables/LegoCam_report.html
```

For a display without recording, use `--align-only`. For a physically changed rig, configure a new source session with legocam.py setup, then use `--source-session NEW_SOURCE --session NEW_GUIDED`. Do not resume an old session after moving the camera or changing focus.
