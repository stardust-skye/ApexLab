"""Lap timing distributions, sectors, consistency and coverage."""

import pandas as pd

from .data import select_drivers


def analyze_laps(data, driver):
    select_drivers(data, [driver])
    frame = data.laps.loc[data.laps["drv"] == driver].copy()
    if frame.empty:
        raise ValueError(f"No recorded laps for {driver}")
    for field in ("time", "s1", "s2", "s3"):
        frame[field] = pd.to_numeric(frame[field], errors="raise")
    valid_time = frame["time"].where(frame["time"] > 0)
    median = valid_time.median()
    frame["seconds_from_median"] = (valid_time - median).abs()
    available = {lap for d, lap in data.coverage["laps_without_telemetry"] if d == driver}
    frame["telemetry_missing"] = frame["lap"].isin(available)
    frame["timing_incomplete"] = (frame[["time", "s1", "s2", "s3"]].isna()
                                    | frame[["time", "s1", "s2", "s3"]].le(0)).any(axis=1)
    ordered = frame.loc[valid_time.notna()]
    def pick(column, method):
        if ordered.empty:
            return None
        index = getattr(ordered[column], method)()
        return int(ordered.loc[index, "lap"])
    return {
        "laps": frame, "timed_laps": int(valid_time.count()), "median_seconds": median,
        "mean_seconds": valid_time.mean(), "std_seconds": valid_time.std(ddof=1),
        "quantiles_seconds": valid_time.quantile([0.25, 0.5, 0.75]).to_dict(),
        "sector_mean_seconds": frame[["s1", "s2", "s3"]].where(frame[["s1", "s2", "s3"]] > 0).mean().to_dict(),
        "fastest_lap": pick("time", "idxmin"), "slowest_lap": pick("time", "idxmax"),
        "most_consistent_lap": pick("seconds_from_median", "idxmin"),
        "missing_lap_numbers_within_recorded_range": sorted(set(range(1, int(frame["lap"].max()) + 1)) - set(frame["lap"])),
        "unmatched_telemetry_laps": [lap for d, lap in data.coverage["telemetry_without_laps"] if d == driver],
    }
