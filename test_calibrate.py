import unittest
from pathlib import Path
from unittest.mock import patch

from calibrate import calibration_steps, check_reference_size, placement_check, finish_collection


class AlignmentTests(unittest.TestCase):
    def test_check_only_pass_keeps_model(self):
        with patch("calibrate.fit") as fit_model, patch("calibrate.summarize"), patch(
            "build_report.build"
        ):
            finish_collection(Path("unused"), [{"role": "validation"}])
            fit_model.assert_not_called()

    def observation(self, centre=(1920, 1516), vertical=False):
        return {
            "centre_px": centre,
            "image_size": [3840, 3032],
            "width_px": 100,
            "length_px": 200,
            "vectors": [[0, 200], [100, 0]] if vertical else [[200, 0], [0, 100]],
        }

    def test_direction_and_centre_gate(self):
        self.assertTrue(placement_check(self.observation(), "H")[0])
        self.assertFalse(placement_check(self.observation(), "V")[0])
        accepted, message = placement_check(self.observation((2000, 1450)), "H")
        self.assertFalse(accepted)
        self.assertIn("LEFT", message)
        self.assertIn("DOWN", message)
        self.assertTrue(placement_check(self.observation(vertical=True), "V")[0])

    def test_wrong_size_gate(self):
        state = {"reference_pixels_per_mm": 10}
        self.assertTrue(check_reference_size(self.observation(), {"block": "B020"}, state)[0])
        self.assertFalse(check_reference_size(self.observation(), {"block": "B040"}, state)[0])

    def test_validation_blocks_are_held_out(self):
        plan = calibration_steps()
        training = {s["block"] for s in plan if s["role"] == "calibration"}
        validation = {s["block"] for s in plan if s["role"] == "validation"}
        self.assertFalse(training & validation)
        for direction in ("H", "V"):
            self.assertGreaterEqual(
                len(
                    {
                        s["block"]
                        for s in plan
                        if s["role"] == "calibration" and s["direction"] == direction
                    }
                ),
                3,
            )
