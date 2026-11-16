# Experiment handoff for the report

The local experiment is in `sessions/reused`. Raw frames from imported placements also remain in `sessions/final_rig/images`. Keep both folders or use the full ZIP backup.

## Confirmed caliper comparisons

| Capture | Arrangement | Camera length × width mm | Caliper length × width mm | Camera minus caliper mm |
|---|---|---|---|---|
| brick_001 | One brick | 31.579 × 15.754 | 31.80 × 15.79 | −0.221 × −0.036 |
| brick_010 | Three bricks in a compact arrangement | 47.657 × 31.624 | 47.64 × 31.79 | +0.017 × −0.166 |

The earlier caliper reading for brick_001 was 31.69 × 15.77 mm; the correction history is preserved in `comparisons/`. Do not count that revision as a new independent calibration observation.

`brick_009` is the long three-brick row, about 95.557 × 15.968 mm optically. Its actual caliper dimensions have not been supplied. `brick_008` is an earlier compact assembly capture, about 47.447 × 32.006 mm; do not automatically assign brick_010's caliper readings to it. No confirmed dedicated two-brick comparison is recorded.

## Reference checks

The checks used for model selection had long-dimension RMSE 0.082 mm with the radial model versus 0.293 mm with the baseline. A later completed reference-check pass, after reconnecting the camera, had length errors −0.115, +0.171 and −0.150 mm, RMSE 0.147 mm. The summary now identifies which completed pass its statistics use. An earlier incomplete pass remains saved and is not included in those current statistics.

The blue detection region was adjusted after that later reference check. Its latest value is recorded in `measurement_roi.json`, and captures from the updated program include `detection_roi`. This does not change the stored calibration coefficients. A complete uncertainty claim must account for the change rather than assuming it has no effect.

## Work remaining for the executive summary

Follow the supplied five-page MTE201 rubric: design/common measurement-system elements, theory and assumptions, calibration procedure/data/curve, deviation plot, maximum uncertainty estimate, systematic/random error discussion, conclusions and recommendations. The assignment permits support-equipment uncertainty to be treated as negligible; state that assumption explicitly if used.

Do not describe RMSE, frame scatter or the largest observed discrepancy as a guaranteed total uncertainty. The proposed 0.01 mm accuracy is unsupported. The largest confirmed LEGO discrepancy so far is about 0.221 mm, but two comparisons do not establish a maximum error over every configuration. Identify unmeasured configurations and unresolved contributors honestly. The current HTML report is a working report, not yet the required five-page executive summary.
