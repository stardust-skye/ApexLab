# Race data acquisition

Run `python scripts/download_race.py` from the project root to acquire one
completed 2026 Grand Prix Race from [TracingInsights/2026](https://github.com/TracingInsights/2026).
Python 3 is the only dependency. Optionally set `GITHUB_TOKEN` for a higher
GitHub API rate limit and use `--workers` to adjust concurrency.

The downloader inspects a pinned upstream commit, preferring Mexico City when
all recorded laps have telemetry. Otherwise it chooses the latest other
completed race with the six required session files and at least one telemetry
file. Completion is determined from the session status and scheduled end time.
Discovery errors stop selection rather than silently skipping races.

Files retain their upstream bytes and paths:

```text
data/raw/2026/<Grand Prix>/Race/
  session_laptimes.json, drivers.json, weather.json, rcm.json
  session_info.json, corners.json
  <driver>/<lap>_tel.json
  download_manifest.json
```

Only the six session files and available per-lap telemetry are downloaded;
practice, qualifying, per-driver `laptimes.json`, radio, images, and caches are
excluded. The manifest records the pinned commit, source URL, byte size,
download timestamp, status, missing recorded laps, and unmatched telemetry.
Existing files are reused only if their JSON, size, and Git blob checksum match
the upstream commit. A missing original timestamp is recorded as `null`.
Invalid local files are replaced atomically. Rerun to resume; failures and
missing upstream telemetry produce a nonzero exit code.

Attribution: data is published by TracingInsights under the repository's
[Apache 2.0 license](https://github.com/TracingInsights/2026/blob/main/LICENSE);
see its [data reference](https://github.com/TracingInsights/2026/blob/main/DATA_REFERENCE.md)
for field definitions and sources, including FastF1, Jolpica, OpenF1 and
MultiViewer. TracingInsights is not affiliated with Formula 1 or the FIA.
Upstream data can be incomplete or contain timing/telemetry anomalies. Coverage
is compared with recorded driver/lap pairs, not a guarantee of valid sensor
samples, and unmatched telemetry may reflect differences between feeds.

## Ingestion and data quality

Install the project's Python dependencies with `pip install -r requirements.txt`,
then run `python -m apexlab.ingestion` from the project root. Optional `--source`
and `--output` paths select another local race and output directory. Output
inside raw data is rejected. Run tests with `python -m unittest discover -s tests`.

The six CSV tables, session and circuit metadata JSON, and
`data_quality_report.json` are written under
`data/processed/2026/United States Grand Prix/Race/`. The report records row
counts, nulls, validation failures with examples, and telemetry coverage.
Validation thresholds are screening bounds, not proof of sensor correctness;
records are retained unchanged when flagged. Missing telemetry is reported,
not interpolated. The detailed [schema and limitations](SCHEMA.md) explains
source field names, units, timestamps, CSV null encoding, and provenance.

For comparison, lap, trace and corner analytics, see the
[analytics guide](../apexlab/analytics/README.md).

## Telemetry explorer

Install the requirements and run
`python -m streamlit run apexlab\dashboard\app.py` from the project root.
The app loads the processed United States race by default; set the
`APEXLAB_DATA_DIR` environment variable to another processed Race directory
containing the four analytics CSVs, session metadata and quality report.
The processed data is cached in memory and reloaded when file size or
modification time changes; regenerate it with ingestion before use. Telemetry
charts show 25 m bin means as markers without connecting or filling gaps.
The app reads but does not modify the processed files.

For observational tire and stint analysis, field availability, model assumptions
and held-out evaluation, see the [research guide](../apexlab/strategy/README.md).
