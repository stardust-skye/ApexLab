"""Leakage-safe historical observation selection."""

import numpy as np
import pandas as pd


def observations_as_of(laps, driver, completed_laps):
    if isinstance(completed_laps, bool) or not isinstance(completed_laps, (int, np.integer)) or completed_laps < 0:
        raise ValueError("completed_laps must be a nonnegative integer")
    if "drv" not in laps or "lap" not in laps:
        raise ValueError("Missing driver/lap fields")
    driver_laps = laps.loc[laps["drv"] == driver]
    lap = pd.to_numeric(driver_laps["lap"], errors="coerce")
    if lap.isna().any() or (~np.isfinite(lap)).any() or (lap < 1).any() or (lap % 1 != 0).any():
        raise ValueError("Invalid source lap numbers")
    return driver_laps.loc[lap <= completed_laps].copy()


def supported_compounds(observations):
    if "compound" not in observations:
        raise ValueError("Source compound field unavailable")
    return sorted({v for v in observations["compound"].dropna().astype(str)
                   if v and v.upper() not in ("NONE", "UNKNOWN")})
