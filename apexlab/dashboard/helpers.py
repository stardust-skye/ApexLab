"""Selection and display helpers; analytics remain in apexlab.analytics."""

import pandas as pd

CHANNELS = {
    "Speed": ("speed", "km/h"), "Throttle": ("throttle", "%"),
    "Brake": ("brake", "fraction"), "RPM": ("rpm", "rpm"), "Gear": ("gear", "gear"),
}
COLORS = ("#ff4b3e", "#36c8ff", "#ffcb62", "#77df9d", "#b794f6")


def driver_options(data):
    return sorted(data.drivers["driver"].dropna().astype(str).unique().tolist())


def lap_options(data, drivers):
    if not drivers or len(drivers) != len(set(drivers)):
        raise ValueError("Select distinct drivers")
    unknown = set(drivers) - set(driver_options(data))
    if unknown:
        raise ValueError(f"Unknown drivers: {sorted(unknown)}")
    lap_values = data.laps.loc[data.laps["drv"].isin(drivers), "lap"]
    tel_values = data.telemetry.loc[data.telemetry["driver"].isin(drivers), "lap"]
    return sorted(set(lap_values.dropna().astype(int)) | set(tel_values.dropna().astype(int)))


def prepare_trace_bins(alignment, selections, channels):
    if not channels or any(channel not in CHANNELS for channel in channels):
        raise ValueError("Select at least one valid telemetry channel")
    if len(selections) != len(set(selections)) or not selections:
        raise ValueError("Select distinct driver/lap pairs")
    bins = alignment["bins"]
    keys = set(zip(bins["driver"], bins["lap"]))
    expected = set(selections)
    if keys - expected:
        raise ValueError("Trace bins contain unexpected driver/lap pairs")
    return bins.sort_values(["driver", "lap", "distance_bin_start_m"])


def format_value(value, suffix="", digits=2):
    if value is None or pd.isna(value):
        return "Unavailable"
    return f"{value:,.{digits}f}{suffix}"
