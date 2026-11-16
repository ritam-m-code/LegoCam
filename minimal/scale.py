"""Turning pixels into millimetres.

The entire calibration is two numbers: how many millimetres one pixel covers
horizontally (sx) and how many it covers vertically (sy). They differ slightly
because camera pixels are not perfectly square and the sensor is rarely dead
parallel to the table.

How the two numbers are found
-----------------------------
Put a gauge block of known length L in view. Its long side shows up as a pixel
vector (dx, dy). Scaling that vector by our two unknowns gives (dx*sx, dy*sy),
and the length of that scaled vector has to come out as L:

    (dx * sx)^2 + (dy * sy)^2 = L^2

The useful part is that this is a straight line in the unknowns sx^2 and sy^2.
Each gauge block capture gives one such equation, and a handful of them are
solved together by least squares. No iteration, no optimiser.

A block lying flat left-to-right has dy near zero, so it says nothing about sy.
That is why the calibration sequence asks for at least one block standing
top-to-bottom: without it the second unknown has nothing holding it down.
"""

import csv
from pathlib import Path

import numpy as np

BLOCKS_FILE = Path(__file__).with_name("blocks.csv")


class CalibrationError(Exception):
    """The gauge block captures cannot produce a usable scale."""


def gauge_blocks():
    """Read the measured gauge block dimensions, keyed by block ID (B020, B100...)."""
    with BLOCKS_FILE.open(newline="", encoding="utf-8-sig") as stream:
        return {
            row["block_id"]: {
                "length_mm": float(row["length_mm"]),
                "width_mm": float(row["width_mm"]),
            }
            for row in csv.DictReader(stream)
        }


def average_edge(edges):
    """Average one part's long edge over several frames, as squared components.

    Squaring first is not an optimisation, it is a correctness fix. The corner
    ordering that `minAreaRect` returns can flip between frames, so the same
    physical edge may be reported as (980, -42) in one frame and (-980, 42) in
    the next. Averaging those directly cancels them to nothing. Averaging
    dx^2 and dy^2 is immune to the flip, and squared components are exactly
    what the fit below consumes.
    """
    squared = np.mean(np.square(np.asarray(edges, dtype=float)), axis=0)
    return squared


def fit(samples):
    """Solve for (sx, sy) in mm per pixel.

    `samples` is a list of (squared_edge, known_length_mm) pairs, where
    squared_edge is the (dx^2, dy^2) returned by `average_edge`.
    """
    if len(samples) < 4:
        raise CalibrationError("At least four gauge block captures are needed.")

    rows = np.array([squared_edge for squared_edge, _ in samples], dtype=float)
    targets = np.array([length_mm**2 for _, length_mm in samples], dtype=float)

    # Dividing each equation by its own target turns absolute residuals into
    # relative ones. Without this a 100 mm block, whose numbers are 25 times
    # larger than a 20 mm block's, would effectively be the only block fitted.
    weighted = rows / targets[:, None]
    _check_solvable(weighted)

    squared_scale, *_ = np.linalg.lstsq(weighted, np.ones(len(samples)), rcond=None)
    if np.any(squared_scale <= 0):
        raise CalibrationError(
            "The fit produced an impossible negative scale. Check that each capture "
            "was labelled with the block that was actually in view."
        )
    return np.sqrt(squared_scale)


def millimetres(sil, scale):
    """Convert a Silhouette to (length_mm, width_mm)."""
    scale = np.asarray(scale, dtype=float)
    length = float(np.linalg.norm(sil.long_edge * scale))
    width = float(np.linalg.norm(sil.short_edge * scale))
    return length, width


def size_from_squared(squared_edge, scale):
    """Length in mm of an edge given its averaged (dx^2, dy^2) from `average_edge`."""
    squared_edge = np.asarray(squared_edge, dtype=float)
    scale = np.asarray(scale, dtype=float)
    return float(np.sqrt(np.sum(squared_edge * np.square(scale))))


def residuals_mm(samples, scale):
    """How far each fitted block lands from its known length. A quick sanity check."""
    return [
        size_from_squared(squared_edge, scale) - length_mm for squared_edge, length_mm in samples
    ]


def _check_solvable(weighted):
    """Catch the 'every block was horizontal' case before lstsq returns nonsense."""
    if np.linalg.matrix_rank(weighted) < 2 or np.linalg.cond(weighted) > 20:
        raise CalibrationError(
            "These captures only constrain one direction. Capture at least one gauge "
            "block standing top-to-bottom as well as the ones lying left-to-right."
        )
