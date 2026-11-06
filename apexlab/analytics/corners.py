"""Compare observed speeds within a distance window around each corner."""

import numpy as np
import pandas as pd

from .data import select_laps


def compare_corners(data, selections, window_m=50.0):
    selections = select_laps(data, selections)
    if not np.isfinite(window_m) or window_m <= 0:
        raise ValueError("window_m must be positive and finite")
    rows = []
    lap_keys = set(zip(data.laps["drv"], data.laps["lap"]))
    for driver, lap in selections:
        tel = data.telemetry.loc[(data.telemetry["driver"] == driver) & (data.telemetry["lap"] == lap)]
        for _, corner in data.corners.iterrows():
            distance = pd.to_numeric(corner["Distance"], errors="coerce")
            if pd.isna(distance) or not np.isfinite(distance):
                raise ValueError(f"Corner {corner['CornerNumber']} has invalid Distance")
            # Suspicious points remain eligible if they lie in the requested window.
            samples = tel.loc[tel["distance"].between(distance - window_m, distance + window_m)]
            rows.append({
                "driver": driver, "lap": lap, "CornerNumber": corner["CornerNumber"],
                "CornerLetter": corner.get("CornerLetter"), "corner_distance_m": distance,
                "corner_source_file": corner["source_file"], "timing_available": (driver, lap) in lap_keys,
                "telemetry_available": not tel.empty, "samples_in_window": len(samples),
                "speed_available_samples": int(samples["speed"].count()),
                "speed_mean_kmh_sample": samples["speed"].mean(),
                "speed_min_kmh_sample": samples["speed"].min(),
                "speed_max_kmh_sample": samples["speed"].max(),
                "distance_flagged_samples": int(samples["flag_distance"].sum()),
                "speed_flagged_samples": int(samples["flag_speed"].sum()),
                "telemetry_source_files": sorted(samples["source_file"].dropna().unique().tolist()),
            })
    return pd.DataFrame(rows)
