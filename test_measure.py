"""Synthetic checks only; these do not establish real-camera accuracy."""

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from legacy.measure import span


class SilhouetteTests(unittest.TestCase):
    def test_blurred_span_and_clipping(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "part.png"
            image = np.full((100, 500), 230, dtype=np.uint8)
            image[20:80, 100:400] = 20
            image = cv2.GaussianBlur(image, (7, 7), 1)
            cv2.imwrite(str(path), image)
            result = span(path, [20, 40, 460, 20])
            self.assertLess(abs(result["pixels"] - 300), 1)
            with self.assertRaisesRegex(ValueError, "boundary"):
                span(path, [110, 40, 350, 20])

    def test_empty_and_disconnected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "part.png"
            image = np.full((100, 500), 230, dtype=np.uint8)
            cv2.imwrite(str(path), image)
            with self.assertRaises(ValueError):
                span(path, [0, 30, 500, 20])
            image[20:80, 100:200] = 20
            image[20:80, 300:400] = 20
            cv2.imwrite(str(path), image)
            # Blur to ensure threshold has interior samples above black level.
            cv2.imwrite(str(path), cv2.GaussianBlur(image, (7, 7), 1))
            with self.assertRaisesRegex(ValueError, "Multiple"):
                span(path, [0, 30, 500, 20])


if __name__ == "__main__":
    unittest.main()
