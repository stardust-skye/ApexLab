"""Driver-level, lap-level and telemetry-sample statistics."""

import pandas as pd

from .data import select_drivers


def compare_drivers(data, drivers):
    drivers = select_drivers(data, drivers, minimum=2)
    result = []
    for driver in drivers:
        laps = data.laps.loc[data.laps["drv"] == driver]
        tel = data.telemetry.loc[data.telemetry["driver"] == driver]
        lap_times = pd.to_numeric(laps["time"], errors="raise")
        lap_times = lap_times.where(lap_times > 0)
        row = {
            "driver": driver, "recorded_laps": len(laps), "timed_laps": int(lap_times.count()),
            "lap_mean_seconds": lap_times.mean(), "lap_std_seconds": lap_times.std(ddof=1),
            "telemetry_samples": len(tel), "speed_mean_kmh_sample": tel["speed"].mean(),
            "speed_max_kmh_sample": tel["speed"].max(), "throttle_mean_pct_sample": tel["throttle"].mean(),
            "brake_active_fraction_sample": tel["brake"].mean(),
            "missing_telemetry_laps": sum(d == driver for d, _ in data.coverage["laps_without_telemetry"]),
            "unmatched_telemetry_laps": sum(d == driver for d, _ in data.coverage["telemetry_without_laps"]),
        }
        for field in ("speed", "throttle", "brake"):
            row[f"{field}_available_samples"] = int(tel[field].count())
            row[f"{field}_flagged_samples"] = int(tel[f"flag_{field}"].sum())
        for field in ("s1", "s2", "s3"):
            sector = pd.to_numeric(laps[field], errors="raise")
            row[f"{field}_mean_seconds"] = sector.where(sector > 0).mean()
            row[f"{field}_available_laps"] = int((sector > 0).sum())
        result.append(row)
    return pd.DataFrame(result)
