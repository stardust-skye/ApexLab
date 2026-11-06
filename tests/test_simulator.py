import unittest
from dataclasses import replace

import numpy as np
import pandas as pd

from apexlab.strategy import construct_stints, fit_stint
from apexlab.strategy.replay import observations_as_of, supported_compounds
from apexlab.strategy.simulator import Assumptions, CompoundPace, compare_scenarios, enumerate_windows, simulate
from test_strategy import fixture


class SimulatorTests(unittest.TestCase):
    def setUp(self):
        self.settings = Assumptions(100, {"SOFT": CompoundPace(0, .2)}, 20, 0, 0, draws=100)
        self.supported = ["SOFT"]

    def run_plan(self, pits, settings=None):
        return simulate(10, pits, ["SOFT"] * (len(pits) + 1), settings or self.settings, self.supported)

    def test_constant_pace_pit_cost_and_distance(self):
        settings = replace(self.settings, compound_pace={"SOFT": CompoundPace(0, 0)})
        no_stop = self.run_plan((), settings)
        one = self.run_plan((4,), settings)
        two = self.run_plan((3, 7), settings)
        self.assertEqual(no_stop["total_seconds"], 1000)
        self.assertEqual(one["total_seconds"], 1020)
        self.assertEqual(two["total_seconds"], 1040)
        self.assertEqual(len(two["laps"]), 10)
        self.assertEqual(two["laps"]["pit_loss_seconds"].sum(), 40)
        self.assertEqual(two["laps"]["assumed_age"].tolist(), [0, 1, 2, 0, 1, 2, 3, 0, 1, 2])

    def test_trend_window_and_comparison(self):
        results = enumerate_windows(10, [(2, 8)], ["SOFT", "SOFT"], self.settings, self.supported)
        self.assertEqual(results.iloc[0]["pit_laps"], (5,))
        self.assertAlmostEqual(results.iloc[0]["total_seconds"], 1024)
        early = self.run_plan((2,))
        best = self.run_plan((5,))
        self.assertAlmostEqual(self.run_plan((3, 7))["total_seconds"], 1042.4)
        self.assertAlmostEqual(self.run_plan(())["total_seconds"], 1009)
        comparison = compare_scenarios([("early", early), ("best", best)])
        self.assertAlmostEqual(comparison.iloc[1]["delta_seconds"], -1.8)

    def test_invalid_plans(self):
        for pits in ((0,), (10,), (3, 3), (4, 3), (2, 3, 4), (1.5,)):
            with self.subTest(pits=pits), self.assertRaises(ValueError):
                self.run_plan(pits)
        for windows in ([(0, 4)], [(4, 2)], [(1, 10)], [(8, 9), (1, 2)]):
            with self.subTest(windows=windows), self.assertRaises(ValueError):
                enumerate_windows(10, windows, ["SOFT"] * (len(windows) + 1), self.settings, self.supported)
        with self.assertRaisesRegex(ValueError, "supported"):
            simulate(10, (5,), ["SOFT", "HARD"], self.settings, self.supported)
        with self.assertRaises(ValueError):
            self.run_plan((5,), replace(self.settings, pit_loss_seconds=-1))
        with self.assertRaises(ValueError):
            self.run_plan((5,), replace(self.settings, baseline_seconds=float("nan")))
        with self.assertRaises(ValueError):
            self.run_plan((5,), replace(self.settings, compound_pace={"SOFT": CompoundPace(-200, 0)}))

    def test_uncertainty_is_seeded_and_changes_interval(self):
        deterministic = self.run_plan((5,))
        noisy = self.run_plan((5,), replace(self.settings, lap_noise_std_seconds=2))
        again = self.run_plan((5,), replace(self.settings, lap_noise_std_seconds=2))
        self.assertEqual(deterministic["interval_90_seconds"], (1024, 1024))
        self.assertGreater(noisy["interval_90_seconds"][1], noisy["interval_90_seconds"][0])
        np.testing.assert_array_equal(noisy["draw_totals"], again["draw_totals"])
        self.assertEqual(noisy["total_seconds"], deterministic["total_seconds"])

    def test_replay_future_observations_do_not_change_context_or_results(self):
        original = fixture()
        altered = original.copy()
        altered.loc[altered.lap > 8, ["compound", "time", "life"]] = ["HARD", 900, 999]
        before = observations_as_of(original, "AAA", 8)
        after = observations_as_of(altered, "AAA", 8)
        pd.testing.assert_frame_equal(before, after)
        self.assertEqual(supported_compounds(before), ["SOFT"])
        self.assertEqual(supported_compounds(after), ["SOFT"])
        b, _ = construct_stints(before)
        a, _ = construct_stints(after)
        self.assertEqual(fit_stint(b)["slope_seconds_per_lap"], fit_stint(a)["slope_seconds_per_lap"])
        self.assertEqual(simulate(10, (5,), ["SOFT", "SOFT"], self.settings, supported_compounds(before))["total_seconds"],
                         simulate(10, (5,), ["SOFT", "SOFT"], self.settings, supported_compounds(after))["total_seconds"])
        self.assertTrue(observations_as_of(original, "AAA", 0).empty)
        with self.assertRaises(ValueError):
            observations_as_of(original, "AAA", -1)
