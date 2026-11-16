import unittest
import tempfile
from pathlib import Path

import numpy as np

from legocam import (
    corrected_vectors,
    dimensions,
    fit_metric,
    fit,
    summarize,
    save_json,
    read_json,
    setup_hash,
)


class MetricTests(unittest.TestCase):
    def test_radial_edge_correction(self):
        observation = {
            "vectors": [[800, 0], [0, 100]],
            "image_size": [3840, 3032],
            "centre_px": [1920, 1516],
        }
        result = corrected_vectors(observation, 1.5)
        self.assertAlmostEqual(result[0, 0], 800 * (1 + 1.5 * (400 / 3840) ** 2))
        groups = []
        for vector in ([[800, 0], [0, 100]], [[0, 400], [100, 0]]):
            item = dict(observation, vectors=vector)
            actual = dimensions(item, [0.1, 0.12], 1.5)
            groups.append(
                {
                    "observations": [item],
                    "reference": {"length_mm": actual[0], "width_mm": actual[1]},
                }
            )
        np.testing.assert_allclose(fit_metric(groups, 1.5), [0.1, 0.12])

    def test_anisotropic_scale_and_rotation(self):
        scales = np.array([0.1, 0.12])
        groups = []
        for length in (15, 30, 60, 100):
            for angle in (0, 0.2, 1.2):
                direction = np.array([np.cos(angle), np.sin(angle)])
                transverse = np.array([-np.sin(angle), np.cos(angle)])
                vectors = np.array([length * direction / scales, 10 * transverse / scales])
                groups.append(
                    {
                        "reference": {"length_mm": length, "width_mm": 10},
                        "observations": [{"vectors": vectors.tolist()}] * 3,
                    }
                )
        actual = fit_metric(groups)
        np.testing.assert_allclose(actual, scales, atol=1e-10)
        for group in groups:
            np.testing.assert_allclose(
                dimensions(group["observations"][0], actual),
                [group["reference"]["length_mm"], 10],
                atol=1e-8,
            )

    def test_rank_deficiency_rejected(self):
        groups = [
            {
                "reference": {"length_mm": 10, "width_mm": 10},
                "observations": [{"vectors": [[10, 10], [10, -10]]}],
            }
        ]
        with self.assertRaises(ValueError):
            fit_metric(groups)

    def test_session_fit_and_held_out_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {"roi": [0, 0, 1000, 500], "width": 1000, "height": 500}
            save_json(root / "setup.json", config)
            for index, length in enumerate((20, 40, 60, 100, 50)):
                record = {
                    "id": str(index),
                    "label": str(index),
                    "role": "calibration" if index < 4 else "validation",
                    "block": f"B{length}",
                    "placement": "centre",
                    "setup_hash": setup_hash(config),
                    "reference": {"length_mm": length, "width_mm": 10, "height_mm": 9.6},
                    "observations": [{"vectors": [[length * 10, 0], [0, 100]]}] * 3,
                }
                save_json(root / "records" / f"{index}.json", record)
            record = {
                "id": "vertical",
                "label": "vertical",
                "role": "calibration",
                "block": "B40",
                "placement": "vertical",
                "setup_hash": setup_hash(config),
                "reference": {"length_mm": 40, "width_mm": 10, "height_mm": 9.6},
                "observations": [{"vectors": [[0, 400], [100, 0]]}] * 3,
            }
            save_json(root / "records" / "vertical.json", record)
            fit(root)
            summarize(root)
            summary = read_json(root / "summary.json")
            self.assertEqual(summary["held_out_block_ids"], ["B50"])
            self.assertLess(summary["length_validation"]["rmse_mm"], 1e-8)
            self.assertTrue((root / "results.csv").exists())
