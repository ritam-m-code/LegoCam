"""The live window.

Nothing here affects a measurement. Detection and fitting always run on the
full-resolution frame; this module only shrinks a copy down to something that
fits on a monitor and draws on it.
"""

import cv2
import numpy as np

PREVIEW_WIDTH = 1000
PREVIEW_HEIGHT = 650
BANNER_HEIGHT = 110

WHITE = (255, 255, 255)
GREY = (200, 200, 200)
GREEN = (0, 220, 0)
AMBER = (0, 190, 255)
YELLOW = (0, 255, 255)
TEAL = (110, 110, 0)


def select_region(frame):
    """Let the user drag a box around where parts will sit. Returns (x, y, w, h)."""
    scale = min(1.0, PREVIEW_WIDTH / frame.shape[1], PREVIEW_HEIGHT / frame.shape[0])
    preview = cv2.resize(frame, None, fx=scale, fy=scale)
    title = "Drag a box around the part, leaving a bright margin. Enter to confirm."
    print(title, flush=True)
    try:
        box = cv2.selectROI(title, preview, fromCenter=False)
    finally:
        cv2.destroyWindow(title)
    if not box[2] or not box[3]:
        raise ValueError("No region selected.")
    return [round(value / scale) for value in box]


def draw(frame, sil, region, lines, ok):
    """Build the window image: a text banner above a marked-up camera preview."""
    scale = min(PREVIEW_WIDTH / frame.shape[1], PREVIEW_HEIGHT / frame.shape[0])
    preview = cv2.resize(frame, None, fx=scale, fy=scale)

    _draw_region(preview, region, scale)
    if sil is not None:
        corners = (sil.corners * scale).astype(np.int32)
        cv2.polylines(preview, [corners], True, GREEN if ok else AMBER, 2)
    _draw_crosshair(preview)

    canvas = np.zeros((preview.shape[0] + BANNER_HEIGHT, preview.shape[1], 3), np.uint8)
    canvas[BANNER_HEIGHT:] = preview
    _draw_banner(canvas, lines, ok)
    return canvas


def _draw_region(preview, region, scale):
    x, y, width, height = region
    top_left = (round(x * scale), round(y * scale))
    bottom_right = (round((x + width) * scale), round((y + height) * scale))
    cv2.rectangle(preview, top_left, bottom_right, TEAL, 1)


def _draw_crosshair(preview):
    """Marks the middle of the image, which is where parts should be placed."""
    cx, cy = preview.shape[1] // 2, preview.shape[0] // 2
    cv2.line(preview, (cx, 0), (cx, preview.shape[0]), TEAL, 1)
    cv2.line(preview, (0, cy), (preview.shape[1], cy), TEAL, 1)
    cv2.drawMarker(preview, (cx, cy), YELLOW, cv2.MARKER_CROSS, 34, 2)


def _draw_banner(canvas, lines, ok):
    heading, instruction, status = lines
    rows = [
        (heading, WHITE, 0.68),
        (instruction, GREY, 0.54),
        (status, GREEN if ok else AMBER, 0.54),
    ]
    for index, (text, colour, size) in enumerate(rows):
        cv2.putText(
            canvas,
            text,
            (14, 28 + index * 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            size,
            colour,
            1,
            cv2.LINE_AA,
        )
