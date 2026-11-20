# Measured reference blocks

Dimensions in reference_blocks.csv were supplied by the user on 2026-11-15, in length × width × height order, using a Mitutoyo 500-196-30 caliper. B015 through B100 identify nominal design lengths, not measured lengths. Values were transcribed without correction; displayed trailing zeros do not imply additional precision.

Repeated readings, measurement temperature, instrument calibration status and per-reference uncertainty have not been supplied. These are caliper-characterized artifacts; no certified gauge-block status or traceability is established by this file. Preserve these readings when later adding repeat measurements.

The measured lengths range from 14.95 to 99.58 mm, widths from 9.91 to 10.03 mm, and heights from 9.57 to 9.69 mm. Height differences can affect apparent scale and should be included when validating the closer camera geometry. Do not average dimensions across different blocks.

For the B100 artifact, capture a fresh image at the new camera height and run:

```powershell
.\.venv\Scripts\python mvp.py calibrate reference_100.png --length 99.58 --reference-measured --reference-width 9.96
```

This is still a single-reference calibration. The CSV is a record, not automatically consumed by mvp.py. To evaluate multiple blocks, capture and measure each separately at the same central position, preserving its block ID in the filename. Compare optical length and width with this table. Reserve some blocks as validation references rather than using every observation for fitting. Later spatial calibration requires observations at known/recorded image positions and orientations, not just this dimension table.
