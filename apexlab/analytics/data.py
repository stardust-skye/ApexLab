"""Load processed data, retaining observations and reference anomalies."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "2026" / "United States Grand Prix" / "Race"
LIMITS = {"speed": (0, 400), "rpm": (0, 25000), "gear": (0, 8),
          "throttle": (0, 100), "brake": (0, 1), "distance": (0, 10000),
          "rel_distance": (0, 1)}


@dataclass
class RaceData:
    drivers: pd.DataFrame
    laps: pd.DataFrame
    telemetry: pd.DataFrame
    corners: pd.DataFrame
    coverage: dict


def _read(directory, name, text):
    return pd.read_csv(directory / f"{name}.csv", keep_default_na=False,
                       na_values=["\\N"], dtype={column: "string" for column in text})


def _validate_laps(frame, label):
    numbers = pd.to_numeric(frame["lap"], errors="coerce")
    invalid = numbers.isna() | ~np.isfinite(numbers) | (numbers < 1) | (numbers % 1 != 0)
    if invalid.any():
        raise ValueError(f"{label} has {int(invalid.sum())} invalid lap numbers")
    frame["lap"] = numbers.astype("int64")


def load_race(directory=DEFAULT_PATH):
    """Load processed CSVs; report missing/unmatched laps and flag anomalies."""
    directory = Path(directory)
    drivers = _read(directory, "drivers", ["driver", "dn", "source_file"])
    laps = _read(directory, "laps", ["drv", "dNum", "source_file", "ms1", "ms2", "ms3", "status"])
    telemetry = _read(directory, "telemetry", ["driver", "DriverAhead", "source_file", "dataKey"])
    corners = _read(directory, "circuit_corners", ["CornerLetter", "CornerLabel", "source_file"])
    for frame, label, required in (
        (drivers, "drivers", ("driver",)),
        (laps, "laps", ("drv", "lap", "source_file", "source_row", "time", "s1", "s2", "s3")),
        (telemetry, "telemetry", ("driver", "lap", "source_file", "source_row", "time", *LIMITS)),
        (corners, "corners", ("CornerNumber", "Distance", "source_file")),
    ):
        missing = set(required) - set(frame.columns)
        if missing:
            raise ValueError(f"{label} missing required columns: {sorted(missing)}")
    if drivers["driver"].isna().any() or drivers["driver"].duplicated().any():
        raise ValueError("drivers contain missing or duplicate driver identifiers")
    for frame, name, column in ((laps, "laps", "drv"), (telemetry, "telemetry", "driver")):
        if frame[column].isna().any():
            raise ValueError(f"{name} contains missing driver identifiers")
        _validate_laps(frame, name)
    if laps.duplicated(["drv", "lap"]).any():
        raise ValueError("duplicate driver/lap timing records")

    driver_ids = set(drivers["driver"])
    unknown_lap_drivers = sorted(set(laps["drv"]) - driver_ids)
    unknown_telemetry_drivers = sorted(set(telemetry["driver"]) - driver_ids)
    lap_keys = set(zip(laps["drv"], laps["lap"]))
    tel_keys = set(zip(telemetry["driver"], telemetry["lap"]))
    telemetry["has_lap_reference"] = pd.MultiIndex.from_frame(
        telemetry[["driver", "lap"]]).isin(lap_keys)
    telemetry["has_driver_reference"] = telemetry["driver"].isin(driver_ids)
    for column, (low, high) in LIMITS.items():
        values = pd.to_numeric(telemetry[column], errors="coerce")
        nonnumeric = telemetry[column].notna() & values.isna()
        if nonnumeric.any():
            raise ValueError(f"telemetry {column} contains {int(nonnumeric.sum())} non-numeric values")
        telemetry[column] = values
        flag = values.notna() & (~np.isfinite(values) | (values < low) | (values > high))
        if column in ("gear", "brake"):
            flag |= values.notna() & (values % 1 != 0)
        telemetry[f"flag_{column}"] = flag
    coverage = {
        "unknown_lap_drivers": unknown_lap_drivers,
        "unknown_telemetry_drivers": unknown_telemetry_drivers,
        "laps_without_telemetry": sorted(lap_keys - tel_keys),
        "telemetry_without_laps": sorted(tel_keys - lap_keys),
    }
    return RaceData(drivers, laps, telemetry, corners, coverage)


def select_drivers(data, drivers, minimum=1):
    drivers = list(drivers)
    if len(drivers) < minimum or len(set(drivers)) != len(drivers):
        raise ValueError(f"Provide at least {minimum} distinct drivers")
    missing = set(drivers) - set(data.drivers["driver"])
    if missing:
        raise ValueError(f"Unknown drivers: {sorted(missing)}")
    return drivers


def select_laps(data, selections, minimum=1):
    selections = list(selections)
    if len(selections) < minimum or len(set(selections)) != len(selections):
        raise ValueError(f"Provide at least {minimum} distinct driver/lap pairs")
    select_drivers(data, list(dict.fromkeys(driver for driver, _ in selections)))
    for _, lap in selections:
        if isinstance(lap, bool) or not isinstance(lap, (int, np.integer)) or lap < 1:
            raise ValueError("Lap numbers must be positive integers")
    return selections
