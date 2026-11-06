"""Within-stint observational linear trend and residual diagnostics."""

import numpy as np
import pandas as pd

from .uncertainty import bootstrap_slope


def fit_stint(laps):
    if "segment_id" not in laps or laps["segment_id"].nunique() != 1:
        raise ValueError("Exactly one source stint segment is required")
    if laps["source_stint"].isna().any():
        raise ValueError("Source stint number is unavailable")
    compounds = laps["compound"].dropna().astype(str).str.upper()
    if len(compounds) != len(laps) or compounds.nunique() != 1 or compounds.iloc[0] in ("", "UNKNOWN", "NONE"):
        raise ValueError("A single known source compound is required")
    selected = laps.loc[laps["eligible"]].copy()
    x = pd.to_numeric(selected["reported_tire_life"], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(selected["time"], errors="coerce").to_numpy(dtype=float)
    if len(x) < 5 or not np.isfinite(x).all() or not np.isfinite(y).all() or np.unique(x).size < 3:
        raise ValueError("Insufficient valid samples: need five laps and three distinct tire-life values")
    if (y <= 0).any() or (x < 0).any():
        raise ValueError("Invalid tire life or lap time")
    design = np.column_stack((np.ones(len(x)), x))
    intercept, slope = np.linalg.lstsq(design, y, rcond=None)[0]
    predictions = design @ np.array([intercept, slope])
    residuals = y - predictions
    median = float(np.median(residuals))
    mad = float(np.median(np.abs(residuals - median)))
    pair_slopes = [(y[j] - y[i]) / (x[j] - x[i]) for i in range(len(x)) for j in range(i + 1, len(x)) if x[j] != x[i]]
    selected["fitted_seconds"] = predictions
    selected["residual_seconds"] = residuals
    selected["residual_outlier"] = np.abs(residuals - median) > 3 * 1.4826 * mad if mad > 0 else False
    return {"n": len(x), "slope_seconds_per_lap": float(slope), "intercept_seconds": float(intercept),
            "slope_interval_95": bootstrap_slope(x, y), "training_rmse_seconds": float(np.sqrt(np.mean(residuals ** 2))),
            "constant_training_rmse_seconds": float(np.sqrt(np.mean((y - y.mean()) ** 2))),
            "median_pairwise_slope_seconds_per_lap": float(np.median(pair_slopes)),
            "residual_mad_seconds": mad, "observations": selected}
