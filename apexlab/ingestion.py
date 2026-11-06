"""Load a TracingInsights race and write analytical CSV tables."""

import argparse
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

from .validation import validate

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "raw" / "2026" / "United States Grand Prix" / "Race"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "2026" / "United States Grand Prix" / "Race"
TELEMETRY_NAME = re.compile(r"([1-9][0-9]*)_tel\.json")
CORNER_COLUMNS = ("CornerNumber", "CornerLetter", "CornerLabel", "X", "Y", "Angle",
                  "Distance", "MVDistance", "Section")


def load_json(path):
    with path.open(encoding="utf-8") as file:
        return json.load(file, parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"{path}: invalid JSON constant {value}")))


def nulls(frame):
    return frame.replace("None", np.nan)


def columns_frame(data, source):
    if not isinstance(data, dict) or not data or any(not isinstance(value, list) for value in data.values()):
        raise ValueError(f"{source}: expected an object of column arrays")
    lengths = {len(value) for value in data.values()}
    if len(lengths) != 1:
        raise ValueError(f"{source}: mismatched column lengths: {sorted(lengths)}")
    frame = nulls(pd.DataFrame(data))
    frame["source_file"] = source
    frame["source_row"] = np.arange(len(frame))
    return frame


def telemetry_frame(path, source, driver, lap):
    obj = load_json(path)
    if not isinstance(obj, dict) or not isinstance(obj.get("tel"), dict):
        raise ValueError(f"{source}: expected a tel object")
    data = obj["tel"]
    if not isinstance(data.get("time"), list):
        raise ValueError(f"{source}: telemetry time must be an array")
    count = len(data["time"])
    arrays = {}
    issues = []
    for key, value in data.items():
        if isinstance(value, list):
            if len(value) != count:
                issues.append({"source_file": source, "field": key, "expected_length": count,
                               "actual_length": len(value), "action": "unassigned"})
                arrays[key] = [None] * count
            else:
                arrays[key] = value
        elif key != "dataKey":
            raise ValueError(f"{source}: unexpected scalar telemetry field {key}")
    frame = nulls(pd.DataFrame(arrays))
    frame["dataKey"] = data.get("dataKey")
    frame["driver"] = driver
    frame["lap"] = lap
    frame["source_file"] = source
    frame["source_row"] = np.arange(count)
    return frame, issues


def ingest(source):
    source = source.resolve()
    metadata = load_json(source / "session_info.json")
    if not isinstance(metadata, dict):
        raise ValueError("session_info.json must contain an object")
    driver_data = load_json(source / "drivers.json")
    if not isinstance(driver_data, dict) or not isinstance(driver_data.get("drivers"), list):
        raise ValueError("drivers.json must contain a drivers array")
    drivers = nulls(pd.DataFrame(driver_data["drivers"]))
    drivers["source_file"] = "drivers.json"
    drivers["source_row"] = np.arange(len(drivers))
    laps = columns_frame(load_json(source / "session_laptimes.json"), "session_laptimes.json")
    weather = columns_frame(load_json(source / "weather.json"), "weather.json")
    race_control = columns_frame(load_json(source / "rcm.json"), "rcm.json")
    corners_data = load_json(source / "corners.json")
    corner_arrays = {key: corners_data[key] for key in CORNER_COLUMNS if key in corners_data}
    corners = columns_frame(corner_arrays, "corners.json")
    corner_metadata = {key: value for key, value in corners_data.items() if key not in CORNER_COLUMNS}
    frames = []
    issues = []
    available = set()
    for path in sorted(source.glob("*/*_tel.json")):
        match = TELEMETRY_NAME.fullmatch(path.name)
        if not match:
            raise ValueError(f"Unrecognized telemetry filename: {path}")
        relative = path.relative_to(source).as_posix()
        frame, found = telemetry_frame(path, relative, path.parent.name, int(match.group(1)))
        frames.append(frame)
        issues.extend(found)
        available.add(relative)
    if not frames:
        raise ValueError(f"No telemetry files found in {source}")
    telemetry = pd.concat(frames, ignore_index=True)
    tables = {"drivers": drivers, "laps": laps, "telemetry": telemetry, "weather": weather,
              "race_control": race_control, "circuit_corners": corners}
    report = validate(tables, metadata, issues)
    expected = {f"{driver}/{lap}_tel.json" for driver, lap in zip(laps["drv"], laps["lap"])
                if pd.notna(driver) and pd.notna(lap)}
    manifest_path = source / "download_manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else None
    listed = {item["filename"] for item in manifest["files"]
              if item["status"] in ("downloaded", "already_valid")} if manifest else set()
    actual = {p.relative_to(source).as_posix() for p in source.glob("*.json")
              if p.name != "download_manifest.json"} | available
    report["source_coverage"] = {
        "source_directory": str(source), "manifest_present": manifest is not None,
        "source_commit": manifest.get("source_commit") if manifest else None,
        "manifest_success_files_missing_locally": sorted(listed - actual),
        "local_files_not_in_manifest": sorted(actual - listed) if manifest else [],
        "recorded_driver_laps": len(expected), "telemetry_files": len(available),
        "recorded_laps_without_telemetry": sorted(expected - available),
        "telemetry_without_recorded_lap": sorted(available - expected),
        "unaligned_arrays": issues,
    }
    return tables, metadata, corner_metadata, report


def json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    if pd.isna(value):
        return None
    raise TypeError(f"Not JSON serializable: {type(value).__name__}")


def write_outputs(output, source, tables, metadata, corner_metadata, report):
    output = output.resolve()
    source = source.resolve()
    raw_root = (ROOT / "data" / "raw").resolve()
    if output == source or source in output.parents or output == raw_root or raw_root in output.parents:
        raise ValueError("Output must not be within the raw data directory")
    documents = {}
    for name, data in (
        ("session_metadata.json", {"source_file": "session_info.json", "data": metadata}),
        ("circuit_metadata.json", {"source_file": "corners.json", "data": corner_metadata}),
        ("data_quality_report.json", report),
    ):
        documents[name] = json.dumps(data, indent=2, ensure_ascii=False, default=json_default,
                                     allow_nan=False) + "\n"
    output.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(output / f"{name}.csv", index=False, na_rep="\\N")
    for name, content in documents.items():
        (output / name).write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        tables, metadata, corners, report = ingest(args.source)
        write_outputs(args.output, args.source, tables, metadata, corners, report)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output), "record_counts": report["record_counts"],
                      "validation_rules_triggered": len(report["validation_failures"]),
                      "coverage": report["source_coverage"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
