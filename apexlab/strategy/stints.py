"""Group consecutive laps by source-reported stint, without inferring tires."""

import numpy as np
import pandas as pd


def construct_stints(laps):
    required = {"drv", "lap", "stint", "compound", "life", "pin", "pout",
                "status", "time", "iacc", "ff1G", "del", "source_file", "source_row"}
    missing = required - set(laps)
    if missing:
        raise ValueError(f"Missing stint source fields: {sorted(missing)}")
    frame = laps.copy()
    numbers = pd.to_numeric(frame["lap"], errors="coerce")
    if numbers.isna().any() or (~np.isfinite(numbers)).any() or (numbers < 1).any() or (numbers % 1 != 0).any():
        raise ValueError("Invalid lap numbers")
    if frame["drv"].isna().any() or frame.duplicated(["drv", "lap"]).any():
        raise ValueError("Missing driver or duplicate driver/lap")
    frame["lap"] = numbers.astype(int)
    frame = frame.sort_values(["drv", "lap"]).reset_index(drop=True)
    stint = pd.to_numeric(frame["stint"], errors="coerce")
    bad_stint = frame["stint"].notna() & (stint.isna() | ~np.isfinite(stint) | (stint < 1) | (stint % 1 != 0))
    if bad_stint.any():
        raise ValueError("Invalid source stint number")
    frame["source_stint"] = stint
    change = (frame["drv"].ne(frame["drv"].shift()) | stint.ne(stint.shift())
              | stint.isna() | stint.shift().isna())
    frame["segment_id"] = change.fillna(True).astype("int64").cumsum()
    age = pd.to_numeric(frame["life"], errors="coerce")
    frame["invalid_tire_life"] = frame["life"].notna() & (age.isna() | ~np.isfinite(age) | (age < 0) | (age % 1 != 0))
    frame["reported_tire_life"] = age.where(~frame["invalid_tire_life"])
    timing = pd.to_numeric(frame["time"], errors="coerce")
    frame["valid_time"] = timing.notna() & np.isfinite(timing) & (timing > 0)
    frame["pit_lap"] = frame["pin"].notna() | frame["pout"].notna()
    frame["green_only"] = frame["status"].astype("string").eq("1").fillna(False)
    frame["eligible"] = (frame["valid_time"] & frame["reported_tire_life"].notna()
                         & ~frame["pit_lap"] & frame["green_only"]
                         & frame["iacc"].eq(True).fillna(False)
                         & frame["ff1G"].eq(False).fillna(False)
                         & frame["del"].eq(False).fillna(False))
    summaries = []
    groups = list(frame.groupby("segment_id", sort=False))
    for index, (segment, group) in enumerate(groups):
        labels = group["compound"].dropna().astype(str)
        labels = sorted({x for x in labels if x and x.upper() not in ("UNKNOWN", "NONE")})
        incomplete = (len(group) != group["lap"].max() - group["lap"].min() + 1
                      or group["reported_tire_life"].isna().any())
        life = group["reported_tire_life"].dropna()
        life_inconsistent = bool((life.diff().dropna() < 0).any())
        previous = groups[index - 1][1] if index else None
        prior_same_driver = previous is not None and previous["drv"].iloc[-1] == group["drv"].iloc[0]
        adjacent = prior_same_driver and previous["lap"].iloc[-1] + 1 == group["lap"].iloc[0]
        boundary_pit = bool(adjacent and (pd.notna(previous["pin"].iloc[-1]) or pd.notna(group["pout"].iloc[0])))
        summaries.append({
            "segment_id": int(segment), "driver": group["drv"].iloc[0],
            "source_stint": group["source_stint"].iloc[0],
            "first_lap": int(group["lap"].min()), "last_lap": int(group["lap"].max()),
            "recorded_laps": len(group), "eligible_laps": int(group["eligible"].sum()),
            "missing_lap_numbers": sorted(set(range(int(group["lap"].min()), int(group["lap"].max()) + 1)) - set(group["lap"])),
            "compound": labels[0] if len(labels) == 1 and group["compound"].notna().all()
                        and not group["compound"].astype(str).str.upper().isin(["UNKNOWN", "NONE", ""]).any() else None,
            "compound_conflict": len(labels) > 1, "incomplete": bool(incomplete),
            "tire_life_decreases": life_inconsistent,
            "pit_entry_observed": bool(group["pin"].notna().any()),
            "pit_exit_observed": bool(group["pout"].notna().any()),
            "start_boundary_pit_observed": boundary_pit,
            "stint_evidence": "source-reported" if group["source_stint"].notna().all() else "unavailable",
        })
    return frame, pd.DataFrame(summaries)
