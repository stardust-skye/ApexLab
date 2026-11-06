"""Distance-bin trace alignment without filling or interpolating observations."""

import numpy as np
import pandas as pd

from .data import select_laps


def align_traces(data, selections, bin_size_m=25.0):
    """Return original selected observations, with distance-bin labels and coverage."""
    selections = select_laps(data, selections, minimum=2)
    if not np.isfinite(bin_size_m) or bin_size_m <= 0:
        raise ValueError("bin_size_m must be positive and finite")
    frames = []
    coverage = []
    lap_keys = set(zip(data.laps["drv"], data.laps["lap"]))
    for driver, lap in selections:
        frame = data.telemetry.loc[(data.telemetry["driver"] == driver) & (data.telemetry["lap"] == lap)].copy()
        coverage.append({"driver": driver, "lap": lap, "timing_available": (driver, lap) in lap_keys,
                         "telemetry_available": not frame.empty, "samples": len(frame)})
        if not frame.empty:
            frames.append(frame)
    if frames:
        samples = pd.concat(frames, ignore_index=True)
    else:
        samples = data.telemetry.iloc[:0].copy()
    usable = samples["distance"].notna() & ~samples["flag_distance"]
    samples["distance_bin_start_m"] = np.nan
    samples.loc[usable, "distance_bin_start_m"] = np.floor(
        samples.loc[usable, "distance"] / bin_size_m) * bin_size_m
    fields = ("speed", "throttle", "brake", "rpm", "gear")
    aggregation = {}
    for field in fields:
        aggregation[f"{field}_mean"] = (field, "mean")
        aggregation[f"{field}_available_samples"] = (field, "count")
        aggregation[f"{field}_flagged_samples"] = (f"flag_{field}", "sum")
    aggregation["sample_count"] = ("source_row", "size")
    summary = samples.loc[usable].groupby(
        ["driver", "lap", "distance_bin_start_m"], as_index=False, observed=True
    ).agg(**aggregation)
    for row in coverage:
        selected = (samples["driver"] == row["driver"]) & (samples["lap"] == row["lap"])
        row["unaligned_samples"] = int((selected & ~usable).sum())
    return {"samples": samples, "bins": summary, "coverage": pd.DataFrame(coverage),
            "bin_size_m": bin_size_m}
