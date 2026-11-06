import unittest

import numpy as np
import pandas as pd

from apexlab.strategy import construct_stints, evaluate_holdout, fit_stint
from apexlab.strategy.uncertainty import bootstrap_slope


def fixture():
    rows = []
    for lap in range(1, 21):
        rows.append({"drv": "AAA", "lap": lap, "stint": 1 if lap <= 10 else 2,
                     "compound": "SOFT", "life": lap if lap <= 10 else lap - 10,
                     "pin": 10.0 if lap == 10 else None,
                     "pout": 11.0 if lap == 11 else None,
                     "status": "1", "time": 100 + .2 * (lap if lap <= 10 else lap - 10),
                     "iacc": True, "ff1G": False, "del": False,
                     "source_file": "session_laptimes.json", "source_row": lap - 1})
    return pd.DataFrame(rows)


class StintTests(unittest.TestCase):
    def test_boundaries_and_filters(self):
        frame = fixture()
        frame.loc[2, "status"] = "126"
        frame.loc[3, "iacc"] = False
        rows, stints = construct_stints(frame)
        self.assertEqual(stints["recorded_laps"].tolist(), [10, 10])
        self.assertTrue(stints.iloc[1]["start_boundary_pit_observed"])
        self.assertFalse(rows.loc[2, "eligible"])
        self.assertFalse(rows.loc[3, "eligible"])
        self.assertFalse(rows.loc[9, "eligible"])
        self.assertFalse(rows.loc[10, "eligible"])
        self.assertEqual(rows.iloc[0]["source_file"], "session_laptimes.json")

    def test_missing_pit_compound_and_gap_are_explicit(self):
        frame = fixture().drop(index=3).copy()
        frame["pin"] = None
        frame["pout"] = None
        frame.loc[1, "compound"] = None
        rows, stints = construct_stints(frame)
        self.assertTrue(stints.iloc[0]["incomplete"])
        self.assertEqual(stints.iloc[0]["missing_lap_numbers"], [4])
        self.assertFalse(stints.iloc[1]["start_boundary_pit_observed"])
        self.assertIsNone(stints.iloc[0]["compound"])
        with self.assertRaisesRegex(ValueError, "compound"):
            fit_stint(rows[rows.segment_id == 1])

    def test_missing_pit_field_and_invalid_values(self):
        with self.assertRaisesRegex(ValueError, "pin"):
            construct_stints(fixture().drop(columns="pin"))
        frame = fixture()
        frame.loc[0, "lap"] = -1
        with self.assertRaisesRegex(ValueError, "lap"):
            construct_stints(frame)
        frame = fixture()
        frame.loc[0, "life"] = -1
        frame.loc[1, "time"] = -5
        rows, _ = construct_stints(frame)
        self.assertTrue(rows.iloc[0]["invalid_tire_life"])
        self.assertFalse(rows.iloc[1]["eligible"])

    def test_missing_stint_and_missing_flags_not_assumed(self):
        frame = fixture()
        frame.loc[0, "stint"] = None
        frame.loc[1, "del"] = None
        rows, summaries = construct_stints(frame)
        self.assertEqual(summaries.iloc[0]["stint_evidence"], "unavailable")
        self.assertFalse(rows.iloc[1]["eligible"])
        with self.assertRaisesRegex(ValueError, "stint"):
            fit_stint(rows[rows.segment_id == rows.iloc[0].segment_id])

    def test_linear_regression_uncertainty_and_residual(self):
        rows, _ = construct_stints(fixture())
        fit = fit_stint(rows[rows.segment_id == 1])
        self.assertAlmostEqual(fit["slope_seconds_per_lap"], .2)
        self.assertAlmostEqual(fit["median_pairwise_slope_seconds_per_lap"], .2)
        self.assertLess(fit["training_rmse_seconds"], 1e-10)
        self.assertAlmostEqual(fit["slope_interval_95"][0], .2)
        self.assertAlmostEqual(fit["slope_interval_95"][1], .2)
        self.assertTrue(np.allclose(fit["observations"]["residual_seconds"], 0))

    def test_insufficient_and_invalid_uncertainty(self):
        rows, _ = construct_stints(fixture())
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            fit_stint(rows[rows.segment_id == 1].head(3))
        with self.assertRaises(ValueError):
            bootstrap_slope([1, 1, 1, 1, 1], [1, 2, 3, 4, 5])
        with self.assertRaises(ValueError):
            bootstrap_slope([1, 2, 3, 4, np.nan], [1, 2, 3, 4, 5])

    def test_holdout_and_prevent_lap_leakage(self):
        rows, _ = construct_stints(fixture())
        train = rows[rows.segment_id == 1]
        test = rows[rows.segment_id == 2]
        evaluation = evaluate_holdout(train, test)
        self.assertLess(evaluation["trend_rmse_seconds"], 1e-9)
        self.assertGreater(evaluation["constant_rmse_seconds"], 0)
        with self.assertRaisesRegex(ValueError, "different"):
            evaluate_holdout(train, train)
        leaked = train.copy()
        leaked["segment_id"] = 42
        with self.assertRaisesRegex(ValueError, "overlapping"):
            evaluate_holdout(train, leaked)
        other = test.copy()
        other["compound"] = "HARD"
        with self.assertRaisesRegex(ValueError, "same reported compound"):
            evaluate_holdout(train, other)


if __name__ == "__main__":
    unittest.main()
