import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from apexlab.ingestion import columns_frame, ingest, telemetry_frame, write_outputs
from apexlab.validation import validate


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def fixture(source):
    write_json(source / "drivers.json", {"drivers": [{"driver": "ABC", "dn": "1", "team": "Team"}]})
    write_json(source / "session_laptimes.json", {
        "drv": ["ABC", "ABC"], "dNum": ["1", "1"], "lap": [1, 2],
        "sesT": [10, 20], "lST": [0, 10], "lSD": ["2026-01-01T00:00:00", "2026-01-01T00:00:10"],
    })
    write_json(source / "weather.json", {"wT": [1], "wAT": [20]})
    write_json(source / "rcm.json", {"time": ["2026-01-01T00:00:00"], "cat": ["Flag"],
                                    "msg": ["Green"], "dNum": ["None"]})
    write_json(source / "corners.json", {"CornerNumber": [1], "CornerLetter": [""],
                                        "X": [1], "Y": [2], "Distance": [100],
                                        "SectionType": ["Straight", "Corner"]})
    write_json(source / "session_info.json", {
        "t0_date": "2026-01-01T00:00:00",
        "session_info": {"StartDate": "2026-01-01T00:00:00", "EndDate": "2026-01-01T02:00:00"},
    })
    tel = {"time": [0, 1], "speed": [100, 120], "rpm": [10000, 11000], "gear": [3, 4],
           "throttle": [50, 80], "brake": [0, 0], "drs": [0, 1], "rel_distance": [0, 1],
           "DistanceToDriverAhead": ["None", 50], "DriverAhead": ["None", "1"],
           "distance": [0, 100], "acc_x": [1, 2], "acc_y": [1, 2, 3],
           "acc_z": [1, 2], "dataKey": "key"}
    write_json(source / "ABC" / "1_tel.json", {"tel": tel})


class IngestionTests(unittest.TestCase):
    def test_ingest_reports_missing_lap_and_unaligned_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "raw"
            fixture(source)
            before = {p: p.read_bytes() for p in source.rglob("*.json")}
            tables, metadata, corner_metadata, report = ingest(source)
            self.assertEqual(len(tables["telemetry"]), 2)
            self.assertTrue(tables["telemetry"]["acc_y"].isna().all())
            self.assertEqual(tables["telemetry"]["speed"].tolist(), [100, 120])
            self.assertEqual(report["source_coverage"]["recorded_laps_without_telemetry"], ["ABC/2_tel.json"])
            self.assertEqual(report["source_coverage"]["unaligned_arrays"][0]["actual_length"], 3)
            self.assertEqual(corner_metadata["SectionType"], ["Straight", "Corner"])
            output = Path(folder) / "processed"
            write_outputs(output, source, tables, metadata, corner_metadata, report)
            self.assertEqual(before, {p: p.read_bytes() for p in source.rglob("*.json")})
            saved = pd.read_csv(output / "circuit_corners.csv", keep_default_na=False, na_values=["\\N"])
            self.assertEqual(saved.loc[0, "CornerLetter"], "")
            self.assertTrue((output / "data_quality_report.json").exists())

    def test_inconsistent_columns_raise(self):
        with self.assertRaisesRegex(ValueError, "mismatched"):
            columns_frame({"a": [1], "b": []}, "test.json")

    def test_output_under_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "race"
            fixture(source)
            tables, metadata, corners, report = ingest(source)
            with self.assertRaisesRegex(ValueError, "raw data"):
                write_outputs(source / "output", source, tables, metadata, corners, report)
            self.assertFalse((source / "output").exists())

    def test_validation_detects_invalid_values_and_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            fixture(source)
            tables, metadata, _, _ = ingest(source)
            tables["laps"] = pd.concat([tables["laps"], tables["laps"].iloc[[0]]], ignore_index=True)
            tables["laps"].loc[0, "lSD"] = "bad timestamp"
            tables["laps"].loc[1, "lap"] = -1
            tables["telemetry"].loc[0, "driver"] = "UNKNOWN"
            tables["telemetry"].loc[0, "speed"] = 500
            tables["telemetry"].loc[0, "time"] = -1
            tables["weather"].loc[0, "wT"] = None
            report = validate(tables, metadata, [])
            rules = {item["rule"] for item in report["validation_failures"]}
            self.assertTrue({"duplicate_key", "invalid_timestamp:lSD", "invalid_lap_number",
                             "missing_driver_reference", "physical_range:speed",
                             "invalid_relative_time:time", "unexpected_null:wT"} <= rules)

    def test_rejects_bad_telemetry_structure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            write_json(path, {"tel": {"time": 1}})
            with self.assertRaisesRegex(ValueError, "time must be an array"):
                telemetry_frame(path, "bad.json", "ABC", 1)


if __name__ == "__main__":
    unittest.main()
