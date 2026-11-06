"""Descriptive bootstrap uncertainty for a within-stint linear slope."""

import numpy as np


def bootstrap_slope(x, y, iterations=2000, seed=42):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if len(x) != len(y) or len(x) < 5 or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("At least five finite paired observations are required")
    if np.unique(x).size < 3 or iterations < 100:
        raise ValueError("At least three distinct ages and 100 bootstrap iterations required")
    rng = np.random.default_rng(seed)
    slopes = []
    for _ in range(iterations):
        sample = rng.integers(0, len(x), len(x))
        sx, sy = x[sample], y[sample]
        centered = sx - sx.mean()
        denominator = centered @ centered
        if denominator > 0:
            slopes.append(float(centered @ (sy - sy.mean()) / denominator))
    if len(slopes) < iterations * .9:
        raise ValueError("Too many degenerate bootstrap samples")
    return tuple(np.quantile(slopes, [0.025, 0.975]))
