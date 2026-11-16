"""Check comparison bookkeeping without opening a camera."""

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from contextlib import redirect_stdout
from io import StringIO

from legocam import read_json, save_json, setup_hash
from run import record_comparison


class ComparisonTests(unittest.TestCase):
    def test_corrected_readings_preserve_history_and_model(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(StringIO()):
            root = Path(directory)
            config = {"width": 1000, "height": 500}
            model = {
                "setup_hash": setup_hash(config),
                "scales_mm_per_px": [0.1, 0.1],
                "radial_k": 0,
                "axis_reference_ranges_mm": [[10, 100], [10, 40]],
                "status": "test",
            }
            save_json(root / "setup.json", config)
            save_json(root / "calibration.json", model)
            save_json(
                root / "records" / "one.json",
                {
                    "id": "one",
                    "label": "brick_001",
                    "role": "measurement",
                    "block": None,
                    "placement": "centre",
                    "setup_hash": setup_hash(config),
                    "observations": [{"vectors": [[315, 0], [0, 157]]}] * 3,
                },
            )
            args = SimpleNamespace(length=31.69, width=15.77, capture="one")
            record_comparison(root, args)
            args.length, args.width = 31.80, 15.79
            record_comparison(root, args)
            comparison = read_json(root / "comparisons" / "one.json")
            self.assertEqual(comparison["previous_readings"][0]["caliper_length_mm"], 31.69)
            self.assertEqual(read_json(root / "calibration.json"), model)
            row = read_json(root / "summary.json")["records"][0]
            self.assertAlmostEqual(row["length_mm"], 31.5)
            self.assertAlmostEqual(row["caliper_length_error_mm"], -0.3)
