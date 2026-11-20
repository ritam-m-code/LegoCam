"""Finding the part in the picture.

The rig is a dark part on a bright backlit surface, so separating the two is
easy: blur away sensor noise, let Otsu's method pick the brightness threshold
for us, and take the largest dark blob.

What we want out of it is not a width and a height in pixels but the two
*edge vectors* of the smallest rectangle that encloses the blob. A part lying
at a slight angle has a long edge of, say, (980, -42) pixels rather than a
tidy 980 pixels across. Keeping the direction is what lets the calibration in
scale.py work out the horizontal and vertical scales separately.
"""

from dataclasses import dataclass

import cv2
import numpy as np


class PartNotFound(Exception):
    """The image did not contain one clean, fully visible part."""


@dataclass
class Silhouette:
    """The enclosing rectangle of one part, in whole-image pixel coordinates."""

    long_edge: np.ndarray  # (dx, dy) along the part's longer side
    short_edge: np.ndarray  # (dx, dy) along the part's shorter side
    centre: np.ndarray  # (x, y) of the rectangle's middle
    corners: np.ndarray  # 4x2, for drawing the outline on screen

    @property
    def length_px(self):
        return float(np.linalg.norm(self.long_edge))

    @property
    def width_px(self):
        return float(np.linalg.norm(self.short_edge))

    @property
    def is_horizontal(self):
        """True when the part's long side runs left-to-right across the image."""
        return abs(self.long_edge[0]) > abs(self.long_edge[1])


def find_part(image, region):
    """Locate the single dark part inside `region` = (x, y, width, height)."""
    x, y, width, height = region
    if min(width, height) < 5 or min(x, y) < 0:
        raise PartNotFound("The measurement region is too small or starts off-image.")
    if x + width > image.shape[1] or y + height > image.shape[0]:
        raise PartNotFound("The measurement region extends past the edge of the image.")

    crop = image[y : y + height, x : x + width]
    grey = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(grey, (5, 5), 0)
    _, dark_pixels = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Order matters: on an empty view the outline check gives a far more useful
    # message than the contrast check would.
    outline = _largest_outline(dark_pixels)
    _check_contrast(grey, dark_pixels)
    _check_fully_inside(outline, width, height)

    rectangle = cv2.minAreaRect(outline)
    corners = cv2.boxPoints(rectangle)

    # boxPoints returns the corners in order, so consecutive differences are
    # the two edge directions. Whichever is longer is the part's length.
    edges = [corners[1] - corners[0], corners[2] - corners[1]]
    edges.sort(key=np.linalg.norm, reverse=True)

    offset = np.array([x, y], dtype=float)
    return Silhouette(
        long_edge=edges[0],
        short_edge=edges[1],
        centre=np.array(rectangle[0], dtype=float) + offset,
        corners=corners + offset,
    )


def _check_contrast(grey, dark_pixels):
    """Refuse to measure an edge the camera can barely see."""
    dark = grey[dark_pixels > 0]
    bright = grey[dark_pixels == 0]
    if not dark.size or not bright.size:
        raise PartNotFound("The region is all background or all part.")
    if np.median(bright) - np.median(dark) < 20:
        raise PartNotFound("Not enough contrast between the part and the backlight.")


def _largest_outline(dark_pixels):
    """Return the biggest dark blob, insisting there is only one real candidate."""
    outlines, _ = cv2.findContours(dark_pixels, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    outlines = sorted(outlines, key=cv2.contourArea, reverse=True)
    if not outlines or cv2.contourArea(outlines[0]) < 25:
        raise PartNotFound("No part found. Check the backlight and the measurement region.")
    if len(outlines) > 1 and cv2.contourArea(outlines[1]) > 0.1 * cv2.contourArea(outlines[0]):
        raise PartNotFound("More than one part in the region. Measure one at a time.")
    return outlines[0]


def _check_fully_inside(outline, width, height):
    """A part touching the edge of the region is being cropped, so it measures short."""
    x, y, w, h = cv2.boundingRect(outline)
    if x <= 1 or y <= 1 or x + w >= width - 1 or y + h >= height - 1:
        raise PartNotFound("The part touches the edge of the region. Leave a bright margin.")
