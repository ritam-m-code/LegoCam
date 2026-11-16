"""Build a printable HTML report from real session records without inventing results."""

import argparse
import base64
import csv
from html import escape
import json
from pathlib import Path


def table(headers, rows):
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{escape(str(h))}</th>" for h in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>"
            for row in rows
        )
        + "</tbody></table>"
    )


def graph(rows, name):
    points = [
        r
        for r in rows
        if r["role"] in ("calibration", "validation") and r[name + "_error_mm"] is not None
    ]
    if not points:
        return "<p>No reference results have been calculated.</p>"
    maximum = max(0.05, max(abs(r[name + "_error_mm"]) for r in points) * 1.2)
    result = [
        f'<svg viewBox="0 0 700 240" role="img" aria-label="{name} reference errors">',
        '<rect width="700" height="240" fill="white"/>',
        '<path d="M65 20 V200 H670 M65 110 H670" stroke="#999" fill="none"/>',
    ]
    for value in (-maximum, 0, maximum):
        y = 110 - value / maximum * 85
        result.append(f'<text x="5" y="{y+4}" font-size="12">{value:+.3f}</text>')
    for value in (0, 25, 50, 75, 100):
        x = 65 + value / 105 * 600
        result.append(f'<text x="{x}" y="220" font-size="12">{value}</text>')
    for row in points:
        measured = row[name + "_mm"] - row[name + "_error_mm"]
        x = 65 + measured / 105 * 600
        y = 110 - row[name + "_error_mm"] / maximum * 85
        color = "#b54708" if row["role"] == "validation" else "#175cd3"
        result.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{color}"><title>{escape(row["label"])}: {row[name+"_error_mm"]:+.4f} mm</title></circle>'
        )
    result.append(
        '<text x="240" y="238" font-size="12">Caliper reference dimension mm</text></svg>'
    )
    return (
        "".join(result)
        + "<p class='caption'>Blue: fitted references. Orange: validation captures. Vertical axis: optical minus caliper dimension in mm.</p>"
    )


def build(session, output):
    refs_path = Path(__file__).with_name("reference_blocks.csv")
    with refs_path.open(newline="", encoding="utf-8-sig") as stream:
        refs = list(csv.DictReader(stream))
    setup = (
        json.loads((session / "setup.json").read_text())
        if (session / "setup.json").exists()
        else None
    )
    summary = (
        json.loads((session / "summary.json").read_text())
        if (session / "summary.json").exists()
        else None
    )
    rows = summary["records"] if summary else []
    records = [
        json.loads(path.read_text()) for path in sorted((session / "records").glob("*.json"))
    ]
    body = [
        "<h1>Optical length and width measurement of LEGO bricks</h1>",
        "<p class='subtitle'>Backlit USB camera measurement system</p>",
        "<h2>Abstract</h2>",
        "<p>A fixed overhead camera and a backlit panel form a silhouette measurement system for the outside length and width of individual 2 by 4 LEGO bricks and longer assemblies. The software captures repeated frames, segments a selected measurement region, fits a rotated rectangle, and converts its edge vectors to millimetres using measured reference artifacts. Results are assessed against references excluded from fitting. Height is outside the measurement scope.</p>",
        (
            "<p>Calibration and measurement results available at report generation are presented below. Performance claims apply only to the tested rig and conditions.</p>"
            if summary
            else "<p><strong>Data collection is in progress. No final calibration, LEGO results or achieved accuracy is claimed in this version.</strong></p>"
        ),
        "<h2>Measurement definition and apparatus</h2>",
        "<p>Length and width are the longer and shorter sides of a rectangle enclosing the detected outer silhouette. For connected assemblies, outside dimensions include seams. Bricks are placed studs up directly on the backlight. The camera is rigidly mounted above the panel and must remain fixed between calibration and measurement. The Arducam 12MP USB camera uses its stock manual-focus lens and a Windows computer. The camera mount was lowered from the earlier prototype before this session; its final physical working distance has not been recorded.</p>",
        "<p>The non-telecentric lens introduces perspective and field distortion. Reference and brick heights must be comparable. An optional approximate radial correction is available; the software does not recover depth or compensate for height. The physical working distance cannot be inferred precisely from enclosure dimensions.</p>",
    ]
    if setup:
        body.append(
            table(
                ["Setting", "Session value"],
                [
                    ["Delivered frame size", f"{setup['width']} × {setup['height']} pixels"],
                    ["Capture backend", setup["backend"]],
                    ["Requested exposure", setup["exposure"]],
                    ["Requested gain", setup["gain"]],
                    ["Measurement ROI x y w h", setup["roi"]],
                ],
            )
        )
    image = session / "latest_preview.jpg"
    if image.exists():
        data = base64.b64encode(image.read_bytes()).decode()
        body.append(
            f'<figure><img src="data:image/jpeg;base64,{data}" alt="Latest captured silhouette with green bounding rectangle"/><figcaption>Latest session capture and detected rectangle. This is an example of detection, not proof of dimensional accuracy.</figcaption></figure>'
        )
    body += [
        "<h2>Reference characterization</h2>",
        "<p>Ten printed reference artifacts were measured with a Mitutoyo 500-196-30 caliper. The manufacturer specification gives 0.01 mm resolution and ±0.02 mm accuracy [1]. Instrument calibration status, temperature, contact-force effects and repeated caliper readings have not yet been established. These values characterize the artifacts; they do not constitute certified gauge-block calibration or demonstrate a traceability chain.</p>",
        table(
            ["Block ID", "Length mm", "Width mm", "Height mm"],
            [[r["block_id"], r["length_mm"], r["width_mm"], r["height_mm"]] for r in refs],
        ),
        "<h2>Image processing and calibration</h2>",
        "<p>Each placement is captured as five saved frames after stream initialization and control requests. The fixed region is converted to grayscale and smoothed with a 5 by 5 Gaussian kernel. Otsu thresholding separates a dark object from its background. Significant additional objects, inadequate contrast and contact with the region boundary are rejected. The largest remaining contour is enclosed with a rotated minimum-area rectangle. This estimator tolerates in-plane rotation but remains sensitive to edge blur, surface shape and silhouette projection.</p>",
        "<p>The two rectangle edge vectors are converted using horizontal and vertical scale parameters s_x and s_y. For an edge vector (dx, dy), the estimated dimension is sqrt((s_x dx)^2 + (s_y dy)^2). The squared measured long reference dimensions give a linear least-squares problem for s_x^2 and s_y^2. Horizontal and vertical reference placements are required. Short reference sides are excluded from fitting because the nearly square cross-section can rest on either face. Relative weighting prevents long dimensions dominating all short dimensions. Each placement contributes its mean squared edge components; individual frames are not treated as independent placements. Positive scales are required.</p>",
        "<p>Calibration uses multiple reference sizes. Selected reference blocks are reserved for checking rather than included in fitting. The baseline diagonal metric can account for different horizontal and vertical scales. An optional radial term maps each image-centred endpoint q to q times (1 + k times squared normalized radius), normalizing radius by the larger image dimension. The coefficient is selected by a bounded search using calibration long-dimension residuals. Corrected edge vectors then enter the metric fit. This is an approximate correction using opposite-side midpoints, with a fixed assumed principal point; it is not a complete intrinsic lens calibration. Neither model includes skew, height dependence or an additive threshold offset. Rotation and position checks remain essential.</p>",
        "<h2>Experimental results</h2>",
    ]
    if summary:
        model = summary["calibration"]
        body.append(
            f"<p>Selected model: {escape(model['model'])}. Radial coefficient k = {model.get('radial_k', 0):.4f}.</p>"
        )
        body.append(
            table(
                ["Calibration quantity", "Value"],
                [
                    ["Horizontal scale mm per pixel", f"{model['scales_mm_per_px'][0]:.8f}"],
                    ["Vertical scale mm per pixel", f"{model['scales_mm_per_px'][1]:.8f}"],
                    ["Held out reference IDs", ", ".join(summary["held_out_block_ids"]) or "None"],
                    ["Validation placements", summary["validation_placements"]],
                ],
            )
        )
        comparison_path = session / "model_comparison.json"
        if comparison_path.exists():
            comparison = json.loads(comparison_path.read_text())
            body.append(
                table(
                    ["Candidate model", "Length check RMSE mm"],
                    [
                        [name, f"{value['length_rmse_mm']:.3f}"]
                        for name, value in comparison["models"].items()
                    ],
                )
            )
            body.append(
                "<p>The B030 and B050 checks were excluded from coefficient fitting, but have been used to compare the candidate models. They are consequently model-selection checks rather than an untouched final test. Subsequent LEGO comparisons are needed. Reference short-side discrepancies remain conditional on knowing which face was down; they must not be presented as confirmed width accuracy.</p>"
            )
        body.append(
            table(
                ["Capture", "Role", "Length mm", "Width mm", "Length error mm", "Width error mm"],
                [
                    [
                        r["label"],
                        r["role"],
                        f"{r['length_mm']:.3f}",
                        f"{r['width_mm']:.3f}",
                        "" if r["length_error_mm"] is None else f"{r['length_error_mm']:+.3f}",
                        "" if r["width_error_mm"] is None else f"{r['width_error_mm']:+.3f}",
                    ]
                    for r in rows
                ],
            )
        )
        for name in ("length", "width"):
            body += [f"<h3>{name.title()} validation</h3>", graph(rows, name)]
            stats = summary[name + "_validation"]
            if stats:
                body.append(
                    f"<p>Across validation placements, bias is {stats['bias_mm']:+.3f} mm, RMSE is {stats['rmse_mm']:.3f} mm, and maximum absolute discrepancy is {stats['max_abs_error_mm']:.3f} mm. These are observed comparison statistics, not a confidence interval or a total uncertainty.</p>"
                )
        brick_checks = [row for row in rows if row.get("caliper_length_mm") is not None]
        if brick_checks:
            body.append("<h3>LEGO caliper comparisons</h3>")
            body.append(
                table(
                    [
                        "Capture",
                        "Optical L W mm",
                        "Caliper L W mm",
                        "Length error mm",
                        "Width error mm",
                    ],
                    [
                        [
                            row["label"],
                            f"{row['length_mm']:.3f} × {row['width_mm']:.3f}",
                            f"{row['caliper_length_mm']:.2f} × {row['caliper_width_mm']:.2f}",
                            f"{row['caliper_length_error_mm']:+.3f}",
                            f"{row['caliper_width_error_mm']:+.3f}",
                        ]
                        for row in brick_checks
                    ],
                )
            )
            body.append(
                "<p>These are individual placement comparisons against the supplied caliper readings. Earlier corrected readings are retained in the session comparison records. They do not establish a guaranteed accuracy or total uncertainty.</p>"
            )
    else:
        body.append(
            f"<p>{len(records)} capture placement(s) have been recorded. Calibration fitting and validation results are not yet available.</p>"
        )
    body += [
        "<h2>Uncertainty evaluation</h2>",
        "<p>Uncertainty is reported separately from pixel resolution and validation error. Standard uncertainties can be combined with sensitivity coefficients and covariance terms; expanded uncertainty additionally requires a stated coverage factor and justification [2, 3]. The present report does not assign an unsupported total uncertainty.</p>",
        table(
            ["Contribution", "Evaluation and current status"],
            [
                [
                    "Reference instrument",
                    "A ±0.02 mm bounded error would give 0.02/sqrt(3) = 0.0115 mm standard uncertainty if a rectangular distribution is justified. A specification is not a certificate.",
                ],
                [
                    "Reference reading and artifact shape",
                    "Repeated contact readings and shape comparisons are needed. Do not assume zero.",
                ],
                [
                    "Frame variation",
                    "Sample standard deviations are recorded per placement in results.csv. Consecutive-frame correlation prevents blindly dividing by sqrt(n).",
                ],
                [
                    "Calibration and shared reference error",
                    "Multiple blocks constrain scale. Shared caliper systematic error cannot be averaged away.",
                ],
                [
                    "Repositioning and field distortion",
                    "Compare independent placements, offsets and orientations. The observed operating envelope must be stated.",
                ],
                [
                    "Height and projection",
                    "Reference heights range from 9.57 to 9.69 mm. Actual brick body height and sensitivity to height remain to be verified.",
                ],
                [
                    "Drift and camera controls",
                    "The driver has returned inconsistent exposure readbacks. Stability across captures needs checking; initial and final check references can reveal drift.",
                ],
            ],
        ),
        "<p>A caliper used to characterize the references and validate the bricks introduces correlated comparison errors. Agreement is useful but is not independent proof of traceable accuracy. Validation RMSE must not be relabelled as expanded uncertainty, and frame repeatability must not stand in for all other contributions.</p>",
        "<h2>Discussion and conclusion</h2>",
        (
            "<p>The system performs camera-based length and width measurement and preserves the evidence needed to assess it. The tables and residual plots describe the collected dataset. Acceptance for a specified accuracy requires sufficient independent validation and completion of the uncertainty budget. No result is generalized beyond tested sizes, positions, orientations, heights and camera settings.</p>"
            if summary
            else "<p>The capture and analysis workflow is implemented, but the experiment is not complete. Final conclusions depend on multi-reference calibration, held-out checks and repeated LEGO measurements. No numerical accuracy or final LEGO dimensions can be concluded yet.</p>"
        ),
        "<h2>Reproducibility and operation</h2>",
        "<p>The project contains legocam.py for session capture, fitting and results, app.py for desktop controls, reference_blocks.csv for artifact dimensions, and automated tests. Raw PNG frames, capture metadata, detected outlines, configuration hashes and results are stored together in the session directory. Setup changes require a new session and recalibration. The WORKFLOW.md file gives the operating procedure. Run build_report.py again after new results to regenerate this report.</p>",
        "<h2>References</h2>",
        '<p>[1] Mitutoyo. ABSOLUTE Digimatic Caliper product specifications. <a href="https://dev.pim.mitutoyo.com/products/small-tool-instruments-and-data-management/calipers/digimatic-calipers/absolute-digimatic-caliper/">Manufacturer specification</a>.</p>',
        '<p>[2] NIST Technical Note 1297. Type B evaluation and combined standard uncertainty. <a href="https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-4-type-b-evaluation-standard-uncertainty">Type B evaluation</a>; <a href="https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-5-combined-standard-uncertainty">Combined standard uncertainty</a>.</p>',
        '<p>[3] NIST Technical Note 1297. <a href="https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-6-expanded-uncertainty">Expanded uncertainty</a>.</p>',
    ]
    css = """body{font-family:Georgia,serif;max-width:900px;margin:45px auto;padding:0 25px;color:#171717;line-height:1.5;font-size:16px}h1,h2,h3{font-family:Arial,sans-serif;color:black;line-height:1.2}h1{font-size:30px;margin-bottom:8px}h2{font-size:22px;margin-top:32px;break-after:avoid}h3{font-size:18px}.subtitle,.caption,figcaption{color:#555;font-size:14px}table{border-collapse:collapse;width:100%;margin:18px 0;font:14px Arial,sans-serif}th,td{border:1px solid #d9d9d9;padding:9px;text-align:left}th{background:#e9edf2}tr:nth-child(even){background:#f7f8fa}thead{display:table-header-group}tr{break-inside:avoid}figure{margin:22px 0}figure img{max-width:100%;max-height:400px;display:block;margin:auto}svg{width:100%;max-height:300px}a{color:#174a80;overflow-wrap:anywhere}@page{size:letter;margin:0.7in}@media print{body{font-size:10pt;max-width:none;margin:0;padding:0}h1{font-size:23pt}h2{font-size:16pt}h3{font-size:12pt}table{font-size:9pt}a{color:black}svg,figure{break-inside:avoid}}"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>LegoCam measurement report</title><style>'
        + css
        + "</style><body>"
        + "\n".join(body)
        + "</body></html>",
        encoding="utf-8",
    )
    print(output.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, default=Path("sessions/final_rig"))
    parser.add_argument("--output", type=Path, default=Path("deliverables/LegoCam_report.html"))
    args = parser.parse_args()
    build(args.session, args.output)
