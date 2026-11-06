"""Race-level timing overview."""

import pandas as pd


def race_overview(data):
    laps = data.laps
    valid = pd.to_numeric(laps["time"], errors="raise")
    valid = valid.where(valid > 0)
    if valid.notna().any():
        fastest = laps.loc[valid.idxmin(), ["drv", "lap", "time"]].to_dict()
    else:
        fastest = None
    return {"drivers": len(data.drivers), "recorded_laps": len(laps),
            "telemetry_samples": len(data.telemetry), "fastest_lap": fastest}
