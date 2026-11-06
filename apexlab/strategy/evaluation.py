"""Explicitly held-out stint comparison with a constant pace baseline."""

import numpy as np
import pandas as pd

from .degradation import fit_stint


def evaluate_holdout(train, validation):
    if train.empty or validation.empty:
        raise ValueError("Both training and validation stints must be nonempty")
    if train["segment_id"].nunique() != 1 or validation["segment_id"].nunique() != 1:
        raise ValueError("Provide exactly one segment per split")
    if train["segment_id"].iloc[0] == validation["segment_id"].iloc[0]:
        raise ValueError("Training and validation must use different stint segments")
    if set(zip(train["drv"], train["lap"])) & set(zip(validation["drv"], validation["lap"])):
        raise ValueError("Training and validation contain overlapping driver/lap records")
    if train["drv"].nunique() != 1 or validation["drv"].nunique() != 1 or train["drv"].iloc[0] != validation["drv"].iloc[0]:
        raise ValueError("Holdout must be from the same driver")
    def compound(frame):
        values = frame["compound"].dropna().astype(str).str.upper()
        if len(values) != len(frame) or values.nunique() != 1 or values.iloc[0] in ("", "UNKNOWN", "NONE"):
            raise ValueError("Both stints need one known compound")
        return values.iloc[0]
    if compound(train) != compound(validation):
        raise ValueError("Holdout must use the same reported compound")
    fit = fit_stint(train)
    test = validation.loc[validation["eligible"]].copy()
    if test.empty:
        raise ValueError("Validation stint has no eligible laps")
    x = pd.to_numeric(test["reported_tire_life"], errors="raise").to_numpy(dtype=float)
    y = pd.to_numeric(test["time"], errors="raise").to_numpy(dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(y).all() or (x < 0).any() or (y <= 0).any():
        raise ValueError("Invalid validation observations")
    predicted = fit["intercept_seconds"] + fit["slope_seconds_per_lap"] * x
    baseline = fit["observations"]["time"].astype(float).mean()
    return {"train_n": fit["n"], "validation_n": len(y),
            "trend_rmse_seconds": float(np.sqrt(np.mean((y - predicted) ** 2))),
            "constant_rmse_seconds": float(np.sqrt(np.mean((y - baseline) ** 2))),
            "train_segment": train["segment_id"].iloc[0], "validation_segment": validation["segment_id"].iloc[0]}
