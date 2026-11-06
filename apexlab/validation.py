"""Non-destructive checks on the analytical tables."""

import pandas as pd


def _examples(frame, mask, columns, limit=10):
    available = [column for column in columns if column in frame.columns]
    selected = frame.loc[mask, available].head(limit).astype(object)
    return selected.where(pd.notna(selected), None).to_dict("records")


def validate(tables, metadata, structural_issues):
    findings = []

    def add(table, rule, mask, columns):
        count = int(mask.sum())
        if count:
            findings.append({"table": table, "rule": rule, "count": count,
                             "examples": _examples(tables[table], mask, columns)})

    for table, keys in {
        "drivers": ["driver"], "laps": ["drv", "lap"],
        "telemetry": ["driver", "lap", "time"],
        "weather": ["wT"], "race_control": ["time", "cat", "msg"],
        "circuit_corners": ["CornerNumber", "CornerLetter"],
    }.items():
        frame = tables[table]
        add(table, "duplicate_key", frame.duplicated(keys, keep=False), keys + ["source_file", "source_row"])

    drivers = tables["drivers"]
    driver_ids = set(drivers["driver"].dropna())
    driver_numbers = set(drivers["dn"].dropna().astype(str))
    for table, driver in (("laps", "drv"), ("telemetry", "driver")):
        frame = tables[table]
        add(table, "missing_driver_reference", frame[driver].notna() & ~frame[driver].isin(driver_ids),
            [driver, "lap", "source_file", "source_row"])
        lap = pd.to_numeric(frame["lap"], errors="coerce")
        add(table, "invalid_lap_number", lap.isna() | (lap < 1) | (lap % 1 != 0),
            [driver, "lap", "source_file", "source_row"])
    driver_lookup = drivers.dropna(subset=["driver", "dn"]).drop_duplicates("driver").set_index("driver")["dn"].astype(str)
    laps = tables["laps"]
    expected_numbers = laps["drv"].map(driver_lookup)
    add("laps", "driver_number_mismatch", expected_numbers.notna() & laps["dNum"].notna()
        & (expected_numbers != laps["dNum"].astype(str)),
        ["drv", "dNum", "lap", "source_file", "source_row"])
    rcm = tables["race_control"]
    add("race_control", "missing_driver_reference", rcm["dNum"].notna() & ~rcm["dNum"].astype(str).isin(driver_numbers),
        ["dNum", "source_file", "source_row"])
    telemetry = tables["telemetry"]
    add("telemetry", "missing_driver_ahead_reference",
        telemetry["DriverAhead"].notna() & ~telemetry["DriverAhead"].astype(str).isin(driver_numbers),
        ["driver", "lap", "time", "DriverAhead", "source_file", "source_row"])

    required = {
        "drivers": ["driver", "dn", "team"],
        "laps": ["drv", "dNum", "lap", "sesT", "lST", "lSD"],
        "telemetry": ["driver", "lap", "time", "speed", "rpm", "gear", "throttle", "brake", "drs"],
        "weather": ["wT"], "race_control": ["time", "cat", "msg"],
        "circuit_corners": ["CornerNumber", "X", "Y", "Distance"],
    }
    for table, columns in required.items():
        for column in columns:
            frame = tables[table]
            add(table, f"unexpected_null:{column}", frame[column].isna(),
                [column, "source_file", "source_row"])

    for table, column in (("laps", "lSD"), ("race_control", "time")):
        frame = tables[table]
        parsed = pd.to_datetime(frame[column], errors="coerce", utc=True, format="ISO8601")
        add(table, f"invalid_timestamp:{column}", frame[column].notna() & parsed.isna(),
            [column, "source_file", "source_row"])
    for table, column in (("laps", "sesT"), ("laps", "lST"), ("telemetry", "time"), ("weather", "wT")):
        frame = tables[table]
        values = pd.to_numeric(frame[column], errors="coerce")
        add(table, f"invalid_relative_time:{column}", frame[column].notna() & (values.isna() | (values < 0)),
            [column, "source_file", "source_row"])
    if pd.isna(pd.to_datetime(metadata.get("t0_date"), errors="coerce", utc=True)):
        findings.append({"table": "session_metadata", "rule": "invalid_timestamp:t0_date",
                         "count": 1, "examples": [{"value": metadata.get("t0_date")}]})
    for column in ("StartDate", "EndDate"):
        value = metadata.get("session_info", {}).get(column)
        if pd.isna(pd.to_datetime(value, errors="coerce")):
            findings.append({"table": "session_metadata", "rule": f"invalid_timestamp:{column}",
                             "count": 1, "examples": [{"value": value}]})

    limits = {"speed": (0, 400), "rpm": (0, 25000), "gear": (0, 8),
              "throttle": (0, 100), "brake": (0, 1), "drs": (0, 1),
              "distance": (0, 10000), "rel_distance": (0, 1),
              "DistanceToDriverAhead": (0, 10000), "acc_x": (-150, 150),
              "acc_y": (-150, 150), "acc_z": (-150, 150)}
    for column, (low, high) in limits.items():
        values = pd.to_numeric(telemetry[column], errors="coerce")
        invalid = telemetry[column].notna() & (values.isna() | (values < low) | (values > high))
        if column in ("gear", "brake", "drs"):
            invalid |= values.notna() & (values % 1 != 0)
        add("telemetry", f"physical_range:{column}", invalid,
            ["driver", "lap", "time", column, "source_file", "source_row"])

    for issue in structural_issues:
        findings.append({"table": "telemetry", "rule": "unaligned_array", "count": 1, "examples": [issue]})
    return {
        "record_counts": {name: int(len(frame)) for name, frame in tables.items()},
        "missing_values": {name: {column: int(count) for column, count in frame.isna().sum().items()}
                           for name, frame in tables.items()},
        "validation_failures": findings,
    }
