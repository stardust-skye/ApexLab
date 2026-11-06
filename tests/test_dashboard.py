import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from apexlab.analytics import RaceData, race_overview
from apexlab.dashboard.helpers import driver_options, format_value, lap_options, prepare_trace_bins
from test_analytics import build_race


def fixture():
    return RaceData(
        drivers=pd.DataFrame({"driver": ["AAA", "BBB"]}),
        laps=pd.DataFrame({"drv": ["AAA", "AAA", "BBB"], "lap": [1, 2, 1],
                           "time": [100.0, None, 90.0]}),
        telemetry=pd.DataFrame({"driver": ["AAA", "BBB"], "lap": [1, 3]}),
        corners=pd.DataFrame(),
        coverage={},
    )


class DashboardHelperTests(unittest.TestCase):
    def test_driver_and_lap_selection_include_recorded_and_unmatched(self):
        data = fixture()
        self.assertEqual(driver_options(data), ["AAA", "BBB"])
        self.assertEqual(lap_options(data, ["AAA", "BBB"]), [1, 2, 3])
        with self.assertRaisesRegex(ValueError, "distinct"):
            lap_options(data, ["AAA", "AAA"])
        with self.assertRaisesRegex(ValueError, "Unknown"):
            lap_options(data, ["BAD"])

    def test_empty_tables_and_missing_values(self):
        data = fixture()
        data.laps = data.laps.iloc[:0]
        data.telemetry = data.telemetry.iloc[:0]
        self.assertEqual(lap_options(data, ["AAA"]), [])
        self.assertIsNone(race_overview(data)["fastest_lap"])
        self.assertEqual(format_value(None), "Unavailable")
        self.assertEqual(format_value(0), "0.00")

    def test_overview_fastest_and_missing(self):
        summary = race_overview(fixture())
        self.assertEqual(summary["fastest_lap"]["drv"], "BBB")
        self.assertEqual(summary["fastest_lap"]["lap"], 1)

    def test_prepare_bins_retains_missing_without_filling(self):
        bins = pd.DataFrame({"driver": ["BBB", "AAA"], "lap": [1, 1],
                             "distance_bin_start_m": [25, 0],
                             "speed_mean": [None, 0.0], "speed_flagged_samples": [0, 1]})
        prepared = prepare_trace_bins({"bins": bins}, [("AAA", 1), ("BBB", 1)], ["Speed"])
        self.assertEqual(prepared.iloc[0]["speed_mean"], 0)
        self.assertTrue(pd.isna(prepared.iloc[1]["speed_mean"]))
        with self.assertRaisesRegex(ValueError, "channel"):
            prepare_trace_bins({"bins": bins}, [("AAA", 1)], ["invalid"])
        with self.assertRaisesRegex(ValueError, "unexpected"):
            prepare_trace_bins({"bins": bins}, [("AAA", 1)], ["Speed"])

    def test_dashboard_pages_and_missing_telemetry(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            build_race(path)
            (path / "session_metadata.json").write_text(json.dumps({"data": {"session_info": {}}}))
            (path / "data_quality_report.json").write_text(json.dumps({"validation_failures": []}))
            app_path = Path(__file__).resolve().parents[1] / "apexlab" / "dashboard" / "app.py"
            with patch.dict(os.environ, {"APEXLAB_DATA_DIR": str(path)}):
                app = AppTest.from_file(str(app_path), default_timeout=30).run()
                for page in ("Driver Comparison", "Telemetry Explorer", "Lap Analysis", "Corner Analysis"):
                    app.sidebar.radio[0].set_value(page).run()
                    self.assertFalse(app.exception, f"{page}: {app.exception}")
                    if page == "Telemetry Explorer":
                        next(widget for widget in app.selectbox if widget.label == "Driver A").set_value("BBB").run()
                        next(widget for widget in app.selectbox if widget.label == "Lap number").set_value(2).run()
                        self.assertTrue(any("telemetry unavailable" in item.value for item in app.warning))
                        self.assertFalse(app.exception)
                    if page == "Corner Analysis":
                        next(widget for widget in app.selectbox if widget.label == "Lap number").set_value(2).run()
                        self.assertTrue(any("telemetry unavailable" in item.value for item in app.warning))
                        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
