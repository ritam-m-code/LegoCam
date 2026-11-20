"""LegoCam.

Three commands, in the order you run them:

    python measure.py setup        pick the camera and the measurement region
    python measure.py calibrate    show it six gauge blocks, get mm per pixel
    python measure.py measure      put a brick in, read its size on screen

Everything is kept in session/. Nothing else is written.
"""

import argparse
import json
from pathlib import Path
import time

import cv2
import numpy as np

import display
import scale
from camera import Camera, CameraError
from silhouette import PartNotFound, find_part

SESSION = Path(__file__).with_name("session")
SETUP_FILE = SESSION / "setup.json"
SCALE_FILE = SESSION / "scale.json"

WINDOW = "LegoCam"
FRAMES_PER_CAPTURE = 5

# Four different blocks is the minimum the fit will accept, and at least one has
# to stand top-to-bottom so the vertical scale is pinned down. Six captures gives
# a little margin on both counts without making calibration a chore.
CALIBRATION_SEQUENCE = [
    ("B100", "across"),
    ("B080", "across"),
    ("B060", "across"),
    ("B040", "across"),
    ("B040", "down"),
    ("B020", "down"),
]


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def command_setup(args):
    """Record the camera settings and the region parts will be placed in."""
    if SETUP_FILE.exists() and not args.replace:
        raise ValueError(f"{SETUP_FILE} already exists. Pass --replace to start over.")

    settings = {
        "camera": args.camera,
        "width": args.width,
        "height": args.height,
        "exposure": args.exposure,
        "gain": args.gain,
    }
    print("Opening the camera. Close any other app that might be using it.", flush=True)
    with Camera(settings) as cam:
        frame = cam.wait_for_first_frame()

    # Record what the camera actually delivered, not what we asked for. Drivers
    # quietly fall back to a lower resolution, and a scale is only valid at the
    # resolution it was fitted at.
    settings["height"], settings["width"] = frame.shape[:2]
    if (settings["width"], settings["height"]) != (args.width, args.height):
        print(
            f"Note: asked for {args.width}x{args.height}, got {settings['width']}x{settings['height']}."
        )

    settings["roi"] = display.select_region(frame)
    SESSION.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(SESSION / "setup_image.png"), frame)
    _write_json(SETUP_FILE, settings)
    print(f"Saved {SETUP_FILE}. Keep the camera, focus and lighting exactly as they are.")


def command_calibrate(_args):
    """Walk through the gauge blocks and solve for mm per pixel."""
    settings = _read_json(SETUP_FILE, "setup")
    run_live(settings, CalibrationTask())


def command_measure(_args):
    """Show live millimetres for whatever is under the camera."""
    settings = _read_json(SETUP_FILE, "setup")
    calibration = _read_json(SCALE_FILE, "calibrate")
    run_live(settings, MeasureTask(calibration["scale_mm_per_px"]))


# --------------------------------------------------------------------------
# The live window
# --------------------------------------------------------------------------


def run_live(settings, task):
    """Show the camera, let the task narrate it, and capture on SPACE."""
    region = settings["roi"]
    message, message_until = "", 0.0

    with Camera(settings) as cam:
        cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
        try:
            while not task.is_finished():
                if cam.error:
                    raise CameraError(cam.error)

                snapshot = cam.latest()
                if snapshot is None:
                    if not _show_waiting("Opening the camera..."):
                        break
                    continue

                frame, age = snapshot
                _check_resolution(frame, settings)
                part, problem = _try_find(frame, region)
                heading, instruction, status, ready = task.describe(part, problem)

                if age > 3:
                    ready, status = False, "Camera frame is stale. Wait a moment."
                if time.monotonic() < message_until:
                    status = message

                canvas = display.draw(frame, part, region, (heading, instruction, status), ready)
                cv2.imshow(WINDOW, canvas)

                key = cv2.waitKey(20) & 0xFF
                if key in (27, ord("q")) or not _window_open():
                    break
                if key == 32 and ready:
                    message = _attempt_capture(cam, region, task)
                    message_until = time.monotonic() + 4
        finally:
            cv2.destroyAllWindows()


def _attempt_capture(cam, region, task):
    """Collect a short burst of frames and hand them to the task."""
    try:
        return task.capture(_collect_burst(cam, region))
    except (PartNotFound, scale.CalibrationError, ValueError) as error:
        return str(error)


def _collect_burst(cam, region):
    """Return FRAMES_PER_CAPTURE silhouettes from consecutive, distinct frames."""
    parts, previous_frame = [], None
    deadline = time.monotonic() + 5
    while len(parts) < FRAMES_PER_CAPTURE:
        if time.monotonic() > deadline:
            raise PartNotFound("Timed out waiting for frames. Is the camera still running?")
        snapshot = cam.latest()
        # The reader thread stores a brand-new array each time, so identity is a
        # reliable way to tell a fresh frame from one we have already measured.
        if snapshot is None or snapshot[0] is previous_frame:
            time.sleep(0.01)
            continue
        previous_frame = snapshot[0]
        parts.append(find_part(previous_frame, region))

    _check_nothing_moved(parts)
    return parts


def _check_nothing_moved(parts):
    """Catch a hand still in shot, or the part being nudged mid-capture.

    Both position and direction are checked. A part that merely spins in place
    keeps the same length, but its edge swings between the x and y axes, and
    those are exactly the components the calibration fit reads. Absolute values
    are used because the reported corner order can flip between frames.
    """
    centres = np.array([part.centre for part in parts])
    edges = np.abs([part.long_edge for part in parts])
    if np.ptp(centres, axis=0).max() > 5 or np.ptp(edges, axis=0).max() > 2:
        raise PartNotFound("The part moved during capture. Keep hands clear and try again.")


def _check_resolution(frame, settings):
    """Stop rather than measure at a resolution the scale was not fitted at.

    Windows camera drivers will quietly hand back a smaller frame if something
    else grabbed the camera first, or if the requested mode is unavailable. The
    picture still looks fine, so nothing else here would notice.
    """
    height, width = frame.shape[:2]
    if (width, height) != (settings["width"], settings["height"]):
        raise CameraError(
            f"The camera is delivering {width}x{height}, but this session was set up at "
            f"{settings['width']}x{settings['height']}, so any measurement would be wrong. "
            "Close other camera apps and try again, or redo setup and calibrate."
        )


def _try_find(frame, region):
    """Find the part, turning a failure into a message rather than an exception."""
    try:
        return find_part(frame, region), ""
    except PartNotFound as error:
        return None, str(error)


def _window_open():
    return cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) >= 1


def _show_waiting(text):
    """Show a plain message while there is no frame yet. False means quit."""
    canvas = np.zeros((300, 700, 3), np.uint8)
    cv2.putText(canvas, text, (24, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
    cv2.imshow(WINDOW, canvas)
    return (cv2.waitKey(50) & 0xFF) not in (27, ord("q")) and _window_open()


# --------------------------------------------------------------------------
# What the live window is being used for
# --------------------------------------------------------------------------


class CalibrationTask:
    """Steps through CALIBRATION_SEQUENCE, then fits and saves the scale."""

    def __init__(self):
        self.blocks = scale.gauge_blocks()
        self.step = 0
        self.samples = []
        self.finished = False

    def is_finished(self):
        return self.finished

    def describe(self, part, problem):
        block_id, orientation = CALIBRATION_SEQUENCE[self.step]
        length_mm = self.blocks[block_id]["length_mm"]
        lying = "left-to-right" if orientation == "across" else "top-to-bottom"

        heading = f"Gauge block {self.step + 1} of {len(CALIBRATION_SEQUENCE)}: {block_id}"
        instruction = f"Place {block_id} ({length_mm:.2f} mm) {lying}, centred on the cross."

        if part is None:
            return heading, instruction, problem, False
        if not _orientation_matches(part, orientation):
            return heading, instruction, f"Turn it so the long side runs {lying}.", False
        return heading, instruction, "Hands clear, then press SPACE.", True

    def capture(self, parts):
        block_id, orientation = CALIBRATION_SEQUENCE[self.step]
        if not all(_orientation_matches(part, orientation) for part in parts):
            raise ValueError("The block turned during capture. Try again.")

        squared_edge = scale.average_edge([part.long_edge for part in parts])
        self.samples.append((squared_edge, self.blocks[block_id]["length_mm"]))
        self.step += 1

        if self.step < len(CALIBRATION_SEQUENCE):
            return f"{block_id} recorded. Swap in the next block."

        self._fit_and_save()
        self.finished = True
        return "Calibration complete."

    def _fit_and_save(self):
        scale_mm_per_px = scale.fit(self.samples)
        errors = scale.residuals_mm(self.samples, scale_mm_per_px)
        _write_json(
            SCALE_FILE,
            {
                "scale_mm_per_px": scale_mm_per_px.tolist(),
                "blocks_used": [block for block, _ in CALIBRATION_SEQUENCE],
                "fit_errors_mm": errors,
            },
        )
        _report_fit(scale_mm_per_px, errors)


class MeasureTask:
    """Reads out millimetres continuously; SPACE prints a steadier average."""

    def __init__(self, scale_mm_per_px):
        self.scale = np.array(scale_mm_per_px, dtype=float)

    def is_finished(self):
        return False

    def describe(self, part, problem):
        heading = "Measuring"
        if part is None:
            return heading, "Place one part inside the box, centred on the cross.", problem, False
        length_mm, width_mm = scale.millimetres(part, self.scale)
        readout = f"Length {length_mm:7.2f} mm      Width {width_mm:7.2f} mm"
        return heading, readout, "SPACE for a steadier average, Q to quit.", True

    def capture(self, parts):
        length_mm = scale.size_from_squared(
            scale.average_edge([part.long_edge for part in parts]), self.scale
        )
        width_mm = scale.size_from_squared(
            scale.average_edge([part.short_edge for part in parts]), self.scale
        )
        print(f"{length_mm:.2f} mm x {width_mm:.2f} mm   ({FRAMES_PER_CAPTURE} frames)", flush=True)
        return f"Measured {length_mm:.2f} x {width_mm:.2f} mm (also printed in the terminal)"


def _orientation_matches(part, orientation):
    return part.is_horizontal == (orientation == "across")


def _report_fit(scale_mm_per_px, errors):
    worst = max(abs(error) for error in errors)
    print(f"\nHorizontal scale: {scale_mm_per_px[0]:.6f} mm per pixel")
    print(f"Vertical scale:   {scale_mm_per_px[1]:.6f} mm per pixel")
    print(f"Largest gap between a fitted block and its known length: {worst:.3f} mm")
    if worst > 0.5:
        print(
            "That is large enough to suggest a block was mislabelled or badly placed. "
            "Consider running calibrate again."
        )
    print(f"Saved {SCALE_FILE}. Now run: python measure.py measure")


# --------------------------------------------------------------------------
# Plumbing
# --------------------------------------------------------------------------


def _read_json(path, hint):
    if not path.exists():
        raise ValueError(f"{path.name} is missing. Run 'python measure.py {hint}' first.")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)

    setup = commands.add_parser("setup", help="Pick the camera and measurement region")
    setup.add_argument("--camera", type=int, default=1)
    setup.add_argument("--width", type=int, default=3840)
    setup.add_argument("--height", type=int, default=3032)
    setup.add_argument("--exposure", type=float, default=-4)
    setup.add_argument("--gain", type=float, default=32)
    setup.add_argument("--replace", action="store_true", help="Overwrite an existing setup")
    setup.set_defaults(run=command_setup)

    calibrate = commands.add_parser("calibrate", help="Show it the gauge blocks")
    calibrate.set_defaults(run=command_calibrate)

    measure = commands.add_parser("measure", help="Live size readout")
    measure.set_defaults(run=command_measure)

    args = parser.parse_args(argv)
    args.run(args)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, CameraError, PartNotFound, scale.CalibrationError) as error:
        raise SystemExit(str(error)) from error
