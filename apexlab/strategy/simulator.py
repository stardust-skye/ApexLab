"""Assumption-driven pit simulations; never accesses race observations."""

from dataclasses import dataclass, replace
from itertools import product
import math
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CompoundPace:
    offset_seconds: float
    trend_seconds_per_lap: float


@dataclass(frozen=True)
class Assumptions:
    baseline_seconds: float
    compound_pace: dict[str, CompoundPace]
    pit_loss_seconds: float
    starting_age: int
    new_tire_age: int
    track_adjustment_seconds: float = 0.0
    lap_noise_std_seconds: float = 0.0
    seed: int = 42
    draws: int = 1000


def _integer(value, name, minimum):
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def simulate(distance, pit_laps, compounds, assumptions, supported_compounds):
    """Simulate remaining race laps; pit lap is relative to simulation start."""
    _integer(distance, "distance", 1)
    if distance > 500:
        raise ValueError("distance cannot exceed 500 laps")
    pit_laps, compounds = tuple(pit_laps), tuple(compounds)
    if len(pit_laps) not in (0, 1, 2):
        raise ValueError("Only zero, one or two stops supported")
    if len(compounds) != len(pit_laps) + 1:
        raise ValueError("Provide one compound per stint")
    for lap in pit_laps:
        _integer(lap, "pit lap", 1)
    if tuple(sorted(set(pit_laps))) != pit_laps or any(lap >= distance for lap in pit_laps):
        raise ValueError("Pit laps must increase and occur before the final lap")
    if not set(compounds) <= set(supported_compounds):
        raise ValueError("All compounds must be supported by observations available at the cutoff")
    if not set(compounds) <= set(assumptions.compound_pace):
        raise ValueError("Each selected compound requires explicit pace assumptions")
    _integer(assumptions.starting_age, "starting_age", 0)
    _integer(assumptions.new_tire_age, "new_tire_age", 0)
    _integer(assumptions.seed, "seed", 0)
    _integer(assumptions.draws, "draws", 1)
    if assumptions.draws > 10000:
        raise ValueError("draws cannot exceed 10000")
    numeric = [assumptions.baseline_seconds, assumptions.pit_loss_seconds,
               assumptions.track_adjustment_seconds, assumptions.lap_noise_std_seconds]
    if not all(math.isfinite(x) for x in numeric) or assumptions.baseline_seconds <= 0:
        raise ValueError("Baseline and adjustments must be finite and baseline positive")
    if assumptions.pit_loss_seconds < 0 or assumptions.lap_noise_std_seconds < 0:
        raise ValueError("Pit loss and uncertainty must be nonnegative")
    for name in set(compounds):
        p = assumptions.compound_pace[name]
        if not math.isfinite(p.offset_seconds) or not math.isfinite(p.trend_seconds_per_lap):
            raise ValueError(f"Nonfinite pace assumptions for {name}")
    rows = []
    stint = 0
    age = assumptions.starting_age
    for lap in range(1, distance + 1):
        pace = assumptions.compound_pace[compounds[stint]]
        lap_time = assumptions.baseline_seconds + pace.offset_seconds + pace.trend_seconds_per_lap * age + assumptions.track_adjustment_seconds
        if not math.isfinite(lap_time) or lap_time <= 0:
            raise ValueError("Assumptions produce a nonpositive or nonfinite lap time")
        pit = lap in pit_laps
        rows.append({"lap": lap, "stint": stint + 1, "compound": compounds[stint],
                     "assumed_age": age, "pace_seconds": lap_time,
                     "pit_loss_seconds": assumptions.pit_loss_seconds if pit else 0.0,
                     "lap_seconds": lap_time + (assumptions.pit_loss_seconds if pit else 0.0)})
        if pit:
            stint += 1
            age = assumptions.new_tire_age
        else:
            age += 1
    table = pd.DataFrame(rows)
    mean = float(table["lap_seconds"].sum())
    noise = np.random.default_rng(assumptions.seed).normal(
        0, assumptions.lap_noise_std_seconds, (assumptions.draws, distance)
    )
    totals = mean + noise.sum(axis=1)
    return {"laps": table, "total_seconds": mean,
            "interval_90_seconds": tuple(float(x) for x in np.quantile(totals, [.05, .95])),
            "draw_totals": totals}


def enumerate_windows(distance, windows, compounds, assumptions, supported_compounds):
    if len(windows) not in (1, 2):
        raise ValueError("Provide one or two pit windows")
    for start, end in windows:
        _integer(start, "window start", 1)
        _integer(end, "window end", 1)
        if start > end or end >= distance:
            raise ValueError("Each window must be ordered and end before the final lap")
    combinations = math.prod(end - start + 1 for start, end in windows)
    if combinations > 5000:
        raise ValueError("Pit windows exceed 5000 combinations")
    results = []
    for stops in product(*(range(start, end + 1) for start, end in windows)):
        if tuple(sorted(set(stops))) != stops:
            continue
        result = simulate(distance, stops, compounds,
                          replace(assumptions, draws=1, lap_noise_std_seconds=0), supported_compounds)
        results.append({"pit_laps": stops, "total_seconds": result["total_seconds"]})
    if not results:
        raise ValueError("Pit windows contain no valid increasing pit laps")
    return pd.DataFrame(results).sort_values(["total_seconds", "pit_laps"]).reset_index(drop=True)


def compare_scenarios(scenarios):
    if not scenarios:
        raise ValueError("At least one scenario required")
    baseline = scenarios[0][1]["total_seconds"]
    return pd.DataFrame([{"scenario": name, "total_seconds": value["total_seconds"],
                          "delta_seconds": value["total_seconds"] - baseline,
                          "p05_seconds": value["interval_90_seconds"][0],
                          "p95_seconds": value["interval_90_seconds"][1]}
                         for name, value in scenarios])
