#!/usr/bin/env python3
"""Download one completed 2026 race from TracingInsights."""

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

OWNER = "TracingInsights"
REPO = "2026"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"
RAW = f"https://raw.githubusercontent.com/{OWNER}/{REPO}"
REQUIRED = (
    "session_laptimes.json", "drivers.json", "weather.json",
    "rcm.json", "session_info.json", "corners.json",
)
TELEMETRY = re.compile(r"^[^/]+/[1-9][0-9]*_tel\.json$")
MEXICO = "Mexico City Grand Prix"


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def request_bytes(url):
    headers = {"User-Agent": "ApexLab-race-downloader", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith(API + "/"):
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == 2 or isinstance(exc, urllib.error.HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def get_json(url):
    return json.loads(request_bytes(url))


def tree(sha, recursive=False):
    result = get_json(f"{API}/git/trees/{sha}" + ("?recursive=1" if recursive else ""))
    if result.get("truncated"):
        raise RuntimeError(f"GitHub tree {sha} is truncated; refusing incomplete inventory")
    return result["tree"]


def raw_url(commit, event, relative):
    return f"{RAW}/{commit}/" + urllib.parse.quote(f"{event}/Race/{relative}", safe="/")


def completed_time(info):
    details = info["session_info"]
    statuses = info["session_status"]["Status"]
    if details["Type"] != "Race" or not any(s in statuses for s in ("Finished", "Finalised")):
        return None
    offset = details["GmtOffset"]
    match = re.fullmatch(r"([+-]?)(\d\d):(\d\d):(\d\d)", offset)
    if not match:
        raise ValueError(f"invalid session UTC offset: {offset!r}")
    delta = dt.timedelta(hours=int(match[2]), minutes=int(match[3]), seconds=int(match[4]))
    if match[1] == "-":
        delta = -delta
    end = dt.datetime.fromisoformat(details["EndDate"]).replace(tzinfo=dt.timezone(delta))
    if end > dt.datetime.now(dt.timezone.utc):
        return None
    return dt.datetime.fromisoformat(details["StartDate"]).replace(tzinfo=dt.timezone(delta))


def inventory(commit, event, race_sha):
    entries = tree(race_sha, recursive=True)
    files = {item["path"]: item for item in entries if item["type"] == "blob"}
    missing = [name for name in REQUIRED if name not in files]
    telemetry = {name for name in files if TELEMETRY.fullmatch(name)}
    if missing or not telemetry:
        return None, [f"missing required files: {missing}", f"telemetry files: {len(telemetry)}"]
    laps = get_json(raw_url(commit, event, "session_laptimes.json"))
    drivers, numbers = laps["drv"], laps["lap"]
    if not isinstance(drivers, list) or not isinstance(numbers, list) or len(drivers) != len(numbers) or not drivers:
        raise ValueError(f"{event}: invalid session lap index")
    expected = set()
    for driver, number in zip(drivers, numbers):
        if not isinstance(driver, str) or not re.fullmatch(r"[A-Za-z0-9]+", driver):
            raise ValueError(f"{event}: invalid driver identifier {driver!r}")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise ValueError(f"{event}: invalid lap number {number!r}")
        expected.add(f"{driver}/{number}_tel.json")
    missing_laps = sorted(expected - telemetry)
    extras = sorted(telemetry - expected)
    selected = {name: files[name] for name in REQUIRED}
    selected.update({name: files[name] for name in telemetry})
    return selected, [missing_laps, extras]


def discover():
    commit = get_json(f"{API}/commits/main")["sha"]
    root = tree(commit)
    races = []
    for event in root:
        if event["type"] != "tree" or not event["path"].endswith(" Grand Prix"):
            continue
        race = next((x for x in tree(event["sha"]) if x["path"] == "Race" and x["type"] == "tree"), None)
        if race is None:
            continue
        try:
            info = get_json(raw_url(commit, event["path"], "session_info.json"))
            start = completed_time(info)
        except (urllib.error.URLError, ValueError, KeyError, TypeError) as exc:
            raise RuntimeError(f"Cannot determine whether {event['path']} Race is complete: {exc}") from exc
        if start is not None:
            races.append((start, event["path"], race["sha"]))
    races.sort(reverse=True)
    if not races:
        raise RuntimeError("No completed races found")
    notes = []
    mexico = next((r for r in races if r[1] == MEXICO), None)
    if mexico:
        selected, coverage = inventory(commit, mexico[1], mexico[2])
        if selected and not coverage[0]:
            return commit, mexico[1], selected, coverage, notes
        notes.append(f"{MEXICO} is not complete: {coverage}")
    for _, event, sha in races:
        if event == MEXICO:
            continue
        selected, coverage = inventory(commit, event, sha)
        if selected:
            return commit, event, selected, coverage, notes
        notes.append(f"{event} is not usable: {coverage}")
    raise RuntimeError("No usable completed race found. " + "; ".join(notes))


def blob_sha(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def reject_non_json_constant(value):
    raise ValueError(f"invalid JSON constant: {value}")


def validated(data, entry):
    json.loads(data, parse_constant=reject_non_json_constant)
    if len(data) != entry["size"] or blob_sha(data) != entry["sha"]:
        raise ValueError("file size or Git blob checksum differs from upstream")


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".apexlab-", delete=False) as handle:
            name = handle.name
            handle.write(data)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def download_one(commit, event, race_dir, name, entry, previous):
    url = raw_url(commit, event, name)
    path = race_dir.joinpath(*PurePosixPath(name).parts)
    record = {"filename": name, "size_bytes": entry["size"], "source_url": url,
              "downloaded_at": None, "status": "failed", "error": None}
    try:
        if path.exists():
            try:
                validated(path.read_bytes(), entry)
            except (ValueError, UnicodeDecodeError, OSError) as exc:
                print(f"Replacing invalid local file {name}: {exc}", file=sys.stderr)
            else:
                record["downloaded_at"] = previous.get("downloaded_at")
                record["status"] = "already_valid"
                return record
        data = request_bytes(url)
        validated(data, entry)
        atomic_write(path, data)
        record["downloaded_at"] = now()
        record["status"] = "downloaded"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError) as exc:
        record["error"] = str(exc)
        print(f"FAILED {name}: {exc}", file=sys.stderr)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent.parent / "data" / "raw" / "2026")
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.workers <= 32:
        parser.error("--workers must be between 1 and 32")
    commit, event, files, coverage, notes = discover()
    missing, extras = coverage
    for note in notes:
        print(note, file=sys.stderr)
    if missing:
        print(f"Incomplete telemetry: {len(missing)} recorded laps missing: {', '.join(missing)}", file=sys.stderr)
    if extras:
        print(f"Telemetry without a matching recorded lap: {', '.join(extras)}", file=sys.stderr)
    race_dir = args.output / event / "Race"
    manifest_path = race_dir / "download_manifest.json"
    previous = {}
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        previous = {item["filename"]: item for item in old["files"] if item.get("source_url") == raw_url(commit, event, item["filename"])}
    print(f"Downloading {event} Race at {commit}: {len(files)} files", flush=True)
    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(download_one, commit, event, race_dir, name, entry, previous.get(name, {}))
                   for name, entry in sorted(files.items())]
        for future in concurrent.futures.as_completed(futures):
            records.append(future.result())
            if len(records) % 100 == 0:
                print(f"Processed {len(records)}/{len(files)}", flush=True)
    for name in missing:
        records.append({"filename": name, "size_bytes": None, "source_url": raw_url(commit, event, name),
                        "downloaded_at": None, "status": "missing_upstream", "error": "Recorded lap has no telemetry file in the upstream tree"})
    records.sort(key=lambda item: item["filename"])
    manifest = {"source_repository": f"https://github.com/{OWNER}/{REPO}", "source_commit": commit,
                "event": event, "session": "Race", "generated_at": now(),
                "selection_notes": notes, "missing_telemetry": missing, "unmatched_telemetry": extras,
                "files": records}
    atomic_write(manifest_path, (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    counts = {status: sum(r["status"] == status for r in records)
              for status in ("downloaded", "already_valid", "failed", "missing_upstream")}
    print(f"Manifest: {manifest_path}\nResults: {counts}")
    return 1 if counts["failed"] or missing else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
