import tempfile
import unittest
from pathlib import Path

import pandas as pd

from apexlab.analytics import load_race, compare_drivers, analyze_laps, align_traces, compare_corners


def build_race(directory):
    drivers = pd.DataFrame([{"driver": "AAA", "dn": "01"}, {"driver": "BBB", "dn": "2"}])
    laps = pd.DataFrame([
        {"drv": "AAA", "lap": 1, "time": 100, "s1": 30, "s2": 30, "s3": 40},
        {"drv": "AAA", "lap": 2, "time": 110, "s1": 35, "s2": 35, "s3": 40},
        {"drv": "AAA", "lap": 3, "time": 120, "s1": None, "s2": 40, "s3": 40},
        {"drv": "BBB", "lap": 1, "time": 105, "s1": 35, "s2": 35, "s3": 35},
    ])
    laps["source_file"] = "session_laptimes.json"
    laps["source_row"] = range(len(laps))
    rows = [
        ("AAA", 1, 0, 0, 100, 110, 0),
        ("AAA", 1, 1, 11, 120, 50, 1),
        ("AAA", 1, 2, -1, 0, None, None),
        ("BBB", 1, 0.1, 9, 200, 80, 1),
        ("BBB", 1, 1.1, 22, 210, 0, 0),
        ("AAA", 4, 0, 0, 0, 0, 0),
    ]
    telemetry = pd.DataFrame(rows, columns=["driver", "lap", "time", "distance", "speed", "throttle", "brake"])
    telemetry["rpm"] = 10000
    telemetry["gear"] = 3
    telemetry["rel_distance"] = 0.5
    telemetry["source_file"] = telemetry["driver"] + "/" + telemetry["lap"].astype(str) + "_tel.json"
    telemetry["source_row"] = telemetry.groupby(["driver", "lap"]).cumcount()
    corners = pd.DataFrame([{"CornerNumber": 1, "CornerLetter": "", "CornerLabel": "1",
                             "Distance": 10, "source_file": "corners.json"}])
    for name, frame in (("drivers", drivers), ("laps", laps), ("telemetry", telemetry), ("circuit_corners", corners)):
        frame.to_csv(directory / f"{name}.csv", index=False, na_rep="\\N")


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        build_race(self.directory)
        self.data = load_race(self.directory)

    def tearDown(self):
        self.tmp.cleanup()

    def test_loader_preserves_gaps_anomalies_and_provenance(self):
        self.assertEqual(self.data.coverage["laps_without_telemetry"], [("AAA", 2), ("AAA", 3)])
        self.assertEqual(self.data.coverage["telemetry_without_laps"], [("AAA", 4)])
        self.assertEqual(self.data.drivers.loc[0, "dn"], "01")
        self.assertEqual(self.data.telemetry["flag_throttle"].sum(), 1)
        self.assertEqual(self.data.telemetry["flag_distance"].sum(), 1)
        self.assertEqual(self.data.telemetry.loc[0, "throttle"], 110)
        self.assertEqual(self.data.telemetry.loc[0, "source_file"], "AAA/1_tel.json")
        self.assertFalse(self.data.telemetry.iloc[-1]["has_lap_reference"])

    def test_driver_comparison_separates_samples_laps_and_missing(self):
        a = compare_drivers(self.data, ["AAA", "BBB"]).set_index("driver").loc["AAA"]
        self.assertEqual(a["recorded_laps"], 3)
        self.assertEqual(a["lap_mean_seconds"], 110)
        self.assertEqual(a["lap_std_seconds"], 10)
        self.assertEqual(a["telemetry_samples"], 4)
        self.assertEqual(a["speed_mean_kmh_sample"], 55)
        self.assertAlmostEqual(a["throttle_mean_pct_sample"], 160 / 3)
        self.assertEqual(a["throttle_flagged_samples"], 1)
        self.assertEqual(a["brake_available_samples"], 3)
        self.assertEqual(a["missing_telemetry_laps"], 2)

    def test_lap_analysis_distribution_and_incomplete(self):
        result = analyze_laps(self.data, "AAA")
        self.assertEqual((result["fastest_lap"], result["slowest_lap"], result["most_consistent_lap"]), (1, 3, 2))
        self.assertEqual(result["median_seconds"], 110)
        self.assertEqual(result["sector_mean_seconds"]["s1"], 32.5)
        self.assertEqual(result["laps"]["timing_incomplete"].sum(), 1)
        self.assertEqual(result["unmatched_telemetry_laps"], [4])

    def test_alignment_retains_samples_and_missing_values_without_interpolation(self):
        result = align_traces(self.data, [("AAA", 1), ("BBB", 1), ("AAA", 2)], bin_size_m=10)
        samples = result["samples"]
        self.assertEqual(len(samples), 5)
        self.assertEqual(samples.loc[0, "distance_bin_start_m"], 0)
        self.assertEqual(samples.loc[3, "distance_bin_start_m"], 0)
        self.assertTrue(pd.isna(samples.loc[2, "distance_bin_start_m"]))
        self.assertEqual(samples.loc[2, "distance"], -1)
        self.assertTrue(pd.isna(samples.loc[2, "throttle"]))
        self.assertFalse(result["coverage"].iloc[2]["telemetry_available"])
        self.assertEqual(result["coverage"].iloc[0]["unaligned_samples"], 1)
        first = result["bins"].query("driver == 'AAA' and distance_bin_start_m == 0").iloc[0]
        self.assertEqual(first["throttle_mean"], 110)
        self.assertEqual(first["throttle_flagged_samples"], 1)

    def test_corners_no_samples_are_null_not_zero(self):
        result = compare_corners(self.data, [("AAA", 1), ("AAA", 2)], window_m=5)
        self.assertEqual(result.iloc[0]["samples_in_window"], 1)
        self.assertEqual(result.iloc[0]["speed_min_kmh_sample"], 120)
        self.assertEqual(result.iloc[1]["samples_in_window"], 0)
        self.assertTrue(pd.isna(result.iloc[1]["speed_min_kmh_sample"]))
        self.assertFalse(result.iloc[1]["telemetry_available"])

    def test_invalid_requests_fail_explicitly(self):
        with self.assertRaises(ValueError):
            compare_drivers(self.data, ["AAA", "AAA"])
        with self.assertRaises(ValueError):
            align_traces(self.data, [("AAA", 1), ("BBB", 1)], 0)
        with self.assertRaises(ValueError):
            compare_corners(self.data, [("BAD", 1)])
        with self.assertRaises(ValueError):
            compare_corners(self.data, [("AAA", -1)])

    def test_missing_laps_and_single_lap_statistics(self):
        result = align_traces(self.data, [("AAA", 2), ("AAA", 3)])
        self.assertTrue(result["samples"].empty)
        self.assertTrue(result["bins"].empty)
        self.assertFalse(result["coverage"]["telemetry_available"].any())
        b = compare_drivers(self.data, ["AAA", "BBB"]).set_index("driver").loc["BBB"]
        self.assertTrue(pd.isna(b["lap_std_seconds"]))
        self.assertEqual(analyze_laps(self.data, "AAA")["missing_lap_numbers_within_recorded_range"], [])
        self.data.laps = self.data.laps.loc[~((self.data.laps["drv"] == "AAA") & (self.data.laps["lap"] == 2))]
        self.assertEqual(analyze_laps(self.data, "AAA")["missing_lap_numbers_within_recorded_range"], [2])

    def test_invalid_references_and_lap_numbers_reported(self):
        path = self.directory / "telemetry.csv"
        telemetry = pd.read_csv(path, keep_default_na=False, na_values=["\\N"])
        telemetry.loc[0, "driver"] = "XXX"
        telemetry.to_csv(path, index=False, na_rep="\\N")
        loaded = load_race(self.directory)
        self.assertEqual(loaded.coverage["unknown_telemetry_drivers"], ["XXX"])
        telemetry.loc[0, "lap"] = 0
        telemetry.to_csv(path, index=False, na_rep="\\N")
        with self.assertRaisesRegex(ValueError, "invalid lap"):
            load_race(self.directory)


if __name__ == "__main__":
    unittest.main()
