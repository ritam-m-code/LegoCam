import unittest

import cv2
import numpy as np

from vision import outline


class OutlineTests(unittest.TestCase):
    def test_dimensions_under_rotation(self):
        for angle in (0, 8, 45, 85):
            with self.subTest(angle=angle):
                image = np.full((600, 600, 3), 230, np.uint8)
                box = cv2.boxPoints(((300, 300), (300, 80), angle)).astype(np.int32)
                cv2.fillConvexPoly(image, box, (20, 20, 20))
                length, width, _ = outline(image, [50, 50, 500, 500])
                self.assertAlmostEqual(length, 300, delta=3)
                self.assertAlmostEqual(width, 80, delta=3)

    def test_clipped_part_rejected(self):
        image = np.full((100, 200, 3), 230, np.uint8)
        image[30:70, 20:180] = 20
        with self.assertRaisesRegex(ValueError, "boundary"):
            outline(image, [40, 10, 150, 80])
