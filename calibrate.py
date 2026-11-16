"""Live crosshair alignment, guided calibration and brick measurement."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import time

import cv2
import numpy as np

from camera import Camera
from vision import select

from legocam import (
    detect,
    dimensions,
    fit,
    read_json,
    references,
    save_json,
    setup_hash,
    summarize,
    records,
)


def calibration_steps():
    steps = []
    for block, directions in (
        ("B100", "H"),
        ("B080", "H"),
        ("B060", "H"),
        ("B040", "HV"),
        ("B020", "HV"),
        ("B015", "HV"),
    ):
        steps.extend(
            {"block": block, "direction": direction, "role": "calibration"}
            for direction in directions
        )
    for block, directions in (("B090", "H"), ("B070", "H"), ("B050", "H"), ("B030", "HV")):
        steps.extend(
            {"block": block, "direction": direction, "role": "validation"}
            for direction in directions
        )
    for repeat in range(3):
        steps.append(
            {"block": "B030", "direction": "H", "role": "validation", "replacement": repeat + 1}
        )
    return steps


def placement_check(observation, direction=None):
    """Keep the approximate optical axis within the central part of the silhouette."""
    centre = np.asarray(observation["centre_px"])
    target = np.asarray(observation["image_size"]) / 2
    vector = np.asarray(observation["vectors"][0])
    angle = abs(float(np.degrees(np.arctan2(vector[1], vector[0])))) % 180
    horizontal = min(angle, 180 - angle) <= 12
    vertical = abs(angle - 90) <= 12
    if direction == "H" and not horizontal:
        return False, "Rotate the LONG side left-to-right"
    if direction == "V" and not vertical:
        return False, "Rotate the LONG side top-to-bottom"
    # Tolerance is proportional to the narrow side, not the reference length.
    tolerance = max(8, min(30, observation["width_px"] * 0.22))
    offset = target - centre
    if np.max(np.abs(offset)) > tolerance:
        horizontal_hint = (
            "RIGHT" if offset[0] > tolerance else "LEFT" if offset[0] < -tolerance else ""
        )
        vertical_hint = "DOWN" if offset[1] > tolerance else "UP" if offset[1] < -tolerance else ""
        return False, "Move block " + " and ".join(h for h in (horizontal_hint, vertical_hint) if h)
    return True, "Centred - remove hands, then press SPACE"


def check_reference_size(observation, step, state):
    scale = state.get("reference_pixels_per_mm")
    if not scale or not step.get("block"):
        return True, ""
    expected = references()[step["block"]]["length_mm"] * scale
    if abs(observation["length_px"] - expected) > max(10, expected * 0.08):
        return False, "Size differs from expected block - check the block ID"
    return True, ""


def save_batch(root, config, step, batch, camera, label, detection_roi=None):
    observations = [item[1] for item in batch]
    centres = np.array([o["centre_px"] for o in observations])
    sizes = np.array([[o["length_px"], o["width_px"]] for o in observations])
    if np.max(np.ptp(centres, axis=0)) > 5 or np.max(np.std(sizes, axis=0)) > 2:
        raise ValueError("Object moved during capture; keep hands clear and retry")
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + "_" + label
    folder = root / "images" / identifier
    folder.mkdir(parents=True)
    images = []
    for index, (frame, _) in enumerate(batch):
        path = folder / f"{index:03}.png"
        if not cv2.imwrite(str(path), frame):
            raise ValueError("Could not save camera image")
        images.append(str(path.relative_to(root)))
    record = {
        "id": identifier,
        "label": label,
        "role": step["role"],
        "block": step.get("block"),
        "placement": "crosshair-" + step.get("direction", "free"),
        "setup_hash": setup_hash(config),
        "images": images,
        "observations": observations,
        "control_set_returned": camera.applied,
        "control_readback": camera.readback,
        "settings_verified": False,
        "alignment_checked": True,
        "detection_roi": detection_roi or config["roi"],
        "replacement": step.get("replacement"),
    }
    if step.get("block"):
        record["reference"] = references()[step["block"]]
    save_json(root / "records" / (identifier + ".json"), record)
    overlay = batch[-1][0].copy()
    cv2.polylines(overlay, [np.asarray(observations[-1]["box"], np.int32)], True, (0, 255, 0), 3)
    cv2.drawMarker(
        overlay,
        (config["width"] // 2, config["height"] // 2),
        (0, 255, 255),
        cv2.MARKER_CROSS,
        80,
        3,
    )
    cv2.imwrite(str(folder / "overlay.png"), overlay)
    cv2.imwrite(str(root / "latest_preview.jpg"), cv2.resize(overlay, (960, 758)))
    return identifier


def render(frame, observation, config, heading, instruction, status, accepted):
    # Display at a manageable size; detection and records use full resolution.
    scale = min(1000 / frame.shape[1], 650 / frame.shape[0])
    preview = cv2.resize(frame, None, fx=scale, fy=scale)
    if observation:
        box = (np.asarray(observation["box"]) * scale).astype(np.int32)
        cv2.polylines(preview, [box], True, (0, 255, 0) if accepted else (0, 165, 255), 2)
    centre = (preview.shape[1] // 2, preview.shape[0] // 2)
    cv2.line(preview, (centre[0], 0), (centre[0], preview.shape[0]), (0, 140, 140), 1)
    cv2.line(preview, (0, centre[1]), (preview.shape[1], centre[1]), (0, 140, 140), 1)
    cv2.drawMarker(preview, centre, (0, 255, 255), cv2.MARKER_CROSS, 34, 2)
    x, y, w, h = config["roi"]
    cv2.rectangle(
        preview,
        (round(x * scale), round(y * scale)),
        (round((x + w) * scale), round((y + h) * scale)),
        (120, 100, 0),
        1,
    )
    canvas = np.zeros((preview.shape[0] + 150, max(1000, preview.shape[1]), 3), np.uint8)
    offset = (canvas.shape[1] - preview.shape[1]) // 2
    canvas[150:, offset : offset + preview.shape[1]] = preview
    for index, (text, color, size) in enumerate(
        (
            (heading, (255, 255, 255), 0.7),
            (instruction, (210, 210, 210), 0.56),
            (status, (0, 255, 0) if accepted else (0, 200, 255), 0.56),
            (
                "SPACE capture | B redraw blue area | Q quit | R retry",
                (190, 190, 190),
                0.5,
            ),
        )
    ):
        cv2.putText(
            canvas,
            text,
            (15, 30 + index * 34),
            cv2.FONT_HERSHEY_SIMPLEX,
            size,
            color,
            1,
            cv2.LINE_AA,
        )
    return canvas


def finish_collection(root, plan):
    """Reference checks must not silently refit a model selected earlier."""
    if any(step["role"] == "calibration" for step in plan):
        fit(root)
    summarize(root)
    from build_report import build

    build(root, root / "report.html")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="sessions/guided")
    parser.add_argument("--source-session", default="sessions/final_rig")
    parser.add_argument(
        "--measure",
        action="store_true",
        help="Live brick measurement using the session calibration",
    )
    parser.add_argument(
        "--align-only", action="store_true", help="Show live alignment without recording"
    )
    parser.add_argument(
        "--plan", type=Path, help="JSON sequence for a shorter collection/check workflow"
    )
    parser.add_argument(
        "--progress-file", default="wizard.json", help="Progress file within the session"
    )
    args = parser.parse_args(argv)
    root = Path(args.session)
    if not (root / "setup.json").exists():
        config = read_json(Path(args.source_session) / "setup.json")
        config.update(
            created_utc=datetime.now(timezone.utc).isoformat(),
            placement_policy="image-centre crosshair",
        )
        save_json(root / "setup.json", config)
    config = read_json(root / "setup.json")
    # Detection bounds can be changed without pretending the lens was recalibrated.
    # Preserve the original setup/model and record the actual region per capture.
    display_config = dict(config)
    region_path = root / "measurement_roi.json"
    if region_path.exists():
        region = read_json(region_path)["roi"]
        x, y, width, height = region
        if (
            min(x, y) < 0
            or min(width, height) < 10
            or x + width > config["width"]
            or y + height > config["height"]
        ):
            raise ValueError("Measurement region is outside the camera image")
        display_config["roi"] = region
    plan = read_json(args.plan) if args.plan else calibration_steps()
    if (
        not isinstance(plan, list)
        or not plan
        or any(
            not isinstance(s, dict)
            or s.get("block") not in references()
            or s.get("direction") not in ("H", "V")
            or s.get("role") not in ("calibration", "validation")
            for s in plan
        )
    ):
        raise ValueError("Invalid calibration/check sequence")
    if Path(args.progress_file).name != args.progress_file:
        raise ValueError("Progress filename must not contain directory components")
    state_path = root / args.progress_file
    state = read_json(state_path) if state_path.exists() else {"step": 0, "completed": []}
    if "reference_pixels_per_mm" not in state and (root / "calibration.json").exists():
        initial_model = read_json(root / "calibration.json")
        state["reference_pixels_per_mm"] = 1 / float(np.mean(initial_model["scales_mm_per_px"]))
    if not (args.measure or args.align_only) and state.get("plan") not in (None, plan):
        raise ValueError("Calibration sequence changed; use a new session directory")
    state["plan"] = plan
    model = None
    if args.measure:
        model = read_json(root / "calibration.json")
        if model["setup_hash"] != setup_hash(config):
            raise ValueError("Setup differs from calibration")
    if state["step"] >= len(plan) and not (args.measure or args.align_only):
        print("Calibration complete. Use --measure for live brick measurements.")
        return
    camera = Camera(config)
    window = "LegoCam live calibration"
    cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)
    last_sequence = -1
    observation = None
    detection_error = "No usable part outline"
    frame = None
    message = "Opening camera - please wait"
    batch = []
    capture_after = None
    measurement_count = 1 + sum(r["role"] == "measurement" for r in records(root))
    notice_until = 0
    try:
        while True:
            if camera.error:
                raise ValueError(camera.error)
            snapshot = camera.snapshot()
            new_frame = snapshot is not None and snapshot[0] != last_sequence
            step = (
                {"role": "measurement"} if args.measure else plan[min(state["step"], len(plan) - 1)]
            )
            if new_frame:
                last_sequence, stamp, frame = snapshot
                try:
                    observation = detect(frame, display_config["roi"])
                    detection_error = ""
                    accepted, placement_message = placement_check(
                        observation, step.get("direction") if not args.align_only else None
                    )
                    if accepted and not args.align_only:
                        size_ok, size_message = check_reference_size(observation, step, state)
                        if not size_ok:
                            accepted, placement_message = False, size_message
                except ValueError as error:
                    detection_error = str(error)
                    observation, accepted, placement_message = None, False, str(error)
                if capture_after is not None and stamp >= capture_after:
                    if not accepted:
                        message = "Capture cancelled: " + placement_message
                        capture_after, batch = None, []
                    else:
                        batch.append((frame.copy(), observation))
                        message = f"Capturing {len(batch)}/5 - keep hands clear"
                        if len(batch) == 5:
                            label = (
                                f"brick_{measurement_count:03}"
                                if args.measure
                                else f"step_{state['step']+1:02}_{step['block']}_{step['direction']}"
                            )
                            try:
                                identifier = save_batch(
                                    root, config, step, batch, camera, label, display_config["roi"]
                                )
                                if args.measure:
                                    summarize(root)
                                    measurement_count += 1
                                    message = "Measurement saved. Swap part and press SPACE."
                                    notice_until = time.monotonic() + 3
                                else:
                                    if "reference_pixels_per_mm" not in state:
                                        state["reference_pixels_per_mm"] = (
                                            float(np.mean([o["length_px"] for _, o in batch]))
                                            / references()[step["block"]]["length_mm"]
                                        )
                                    state["completed"].append(identifier)
                                    state["step"] += 1
                                    save_json(state_path, state)
                                    message = "Saved. Place the next block shown above."
                                    notice_until = time.monotonic() + 3
                                    if state["step"] == len(plan):
                                        finish_collection(root, plan)
                                        print(f"Finished. Results and report: {root.resolve()}")
                                        break
                            except ValueError as error:
                                message = str(error)
                                notice_until = time.monotonic() + 5
                            finally:
                                capture_after, batch = None, []
            if frame is None:
                canvas = np.zeros((600, 1000, 3), np.uint8)
                cv2.putText(
                    canvas, message, (30, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1
                )
            else:
                accepted, placement_message = (
                    placement_check(
                        observation, step.get("direction") if not args.align_only else None
                    )
                    if observation
                    else (False, detection_error or "No usable part outline")
                )
                if accepted and not args.align_only:
                    size_ok, size_message = check_reference_size(observation, step, state)
                    if not size_ok:
                        accepted, placement_message = False, size_message
                if snapshot and time.monotonic() - snapshot[1] > 3:
                    accepted, placement_message = False, "Camera frame is stale - wait"
                if args.measure:
                    heading = "Live brick measurement - provisional"
                    instruction = "Centre the whole part on the yellow cross. Keep settings fixed."
                    if observation and model:
                        length, width = dimensions(
                            observation, model["scales_mm_per_px"], model.get("radial_k", 0)
                        )
                        instruction = f"Length {length:.2f} mm   Width {width:.2f} mm   (uncertainty not yet established)"
                else:
                    heading = (
                        "Live alignment"
                        if args.align_only
                        else f"Step {state['step']+1}/{len(plan)} - {step['block']} - {step['role']}"
                    )
                    instruction = (
                        "Centre the block on the yellow cross."
                        if args.align_only
                        else f"{references()[step['block']]['length_mm']:.2f} mm long side {'LEFT-TO-RIGHT' if step['direction'] == 'H' else 'TOP-TO-BOTTOM'}; same face down"
                    )
                    if step.get("replacement") and not args.align_only:
                        instruction = f"REMOVE and REPLACE B030, repeat {step['replacement']}/3; long side LEFT-TO-RIGHT"
                status = (
                    message
                    if capture_after is not None
                    or time.monotonic() < notice_until
                    or message.startswith(("Capture cancelled", "Object moved"))
                    else placement_message
                )
                canvas = render(
                    frame, observation, display_config, heading, instruction, status, accepted
                )
            cv2.imshow(window, canvas)
            key = cv2.waitKey(20) & 0xFF
            if key in (27, ord("q")) or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord("b") and frame is not None and capture_after is None:
                try:
                    region = select(frame)
                    # Check the proposed crop before replacing the previous region.
                    detect(frame, region)
                    save_json(
                        region_path,
                        {
                            "roi": region,
                            "previous_roi": display_config["roi"],
                            "reason": "Measurement region selected in live view",
                            "verification_required": True,
                        },
                    )
                    display_config["roi"] = region
                    observation = None
                    message = "Blue area updated. Recheck references after changing the region."
                    notice_until = time.monotonic() + 4
                except (ValueError, cv2.error) as error:
                    message = "Region unchanged: " + str(error)
                    notice_until = time.monotonic() + 5
            if key == ord("r"):
                message = "Retry when centred"
                capture_after, batch = None, []
            if key == 32 and frame is not None and capture_after is None and not args.align_only:
                accepted, reason = (
                    placement_check(observation, step.get("direction"))
                    if observation
                    else (False, "No usable part")
                )
                if accepted:
                    size_ok, size_message = check_reference_size(observation, step, state)
                    if not size_ok:
                        accepted, reason = False, size_message
                if accepted and time.monotonic() - snapshot[1] <= 3:
                    capture_after = time.monotonic() + 1.5
                    batch = []
                    message = "Capture starting - hands clear"
                else:
                    message = "Capture cancelled: " + reason
    finally:
        camera.stop.set()
        cv2.destroyAllWindows()
        camera.thread.join(timeout=3)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, cv2.error) as error:
        raise SystemExit(str(error)) from error
