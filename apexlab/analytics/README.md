# Telemetry analytics

Install `requirements.txt` and first generate processed data as described in
[`data/README.md`](../../data/README.md). Run examples from the project root:

```python
from apexlab.analytics import (
    load_race, race_overview, compare_drivers, analyze_laps, align_traces, compare_corners,
)

race = load_race()  # optionally pass a processed Race directory
print(race_overview(race))  # race counts and fastest positive recorded lap
print(race.coverage)
drivers = compare_drivers(race, ["VER", "NOR"])
laps = analyze_laps(race, "VER")
print(laps["fastest_lap"], laps["sector_mean_seconds"])
traces = align_traces(race, [("VER", 1), ("NOR", 1)], bin_size_m=25)
samples = traces["samples"]  # original observations, provenance and flags
bins = traces["bins"]        # per-driver/lap/bin summaries
coverage = traces["coverage"]
corners = compare_corners(race, [("VER", 1), ("NOR", 1)], window_m=50)
```

## Data contracts and coverage

`load_race` reads the four processed CSV tables without modifying them. Driver
codes, driver numbers, and provenance are kept as strings; `\N` is missing and
empty strings remain empty. Invalid lap numbers, duplicate lap timing keys,
missing/duplicate driver IDs or malformed required columns raise an error.
Unknown driver references, lap timings without telemetry, and telemetry without
lap timings are recorded in `race.coverage`. Telemetry rows have
`has_driver_reference` and `has_lap_reference`. Analysis requests require
known, distinct drivers or driver/lap pairs; a known but absent lap is not
invented and is reported as unavailable. `source_file` and zero-based
`source_row` are preserved on original lap and telemetry observations.

The known source gap is BOT lap 50 (recorded timing, no telemetry). BOT lap
51 has telemetry without a matching recorded lap. Its two acceleration fields
were left missing during ingestion due to mismatched array lengths. Consult the
[data quality report](../../data/README.md) and
[schema](../../data/SCHEMA.md) before analysis.

## Metrics

`compare_drivers` returns one row per driver. Timing mean and sample standard
deviation (`ddof=1`) are **lap-level**, using available positive lap times;
one or zero values produce an unavailable standard deviation. Per-sector
means are in seconds and use positive available sector times. Speed mean and
maximum (km/h), throttle mean (%) and brake-active fraction (0–1) are
**telemetry-sample-level**, not time- or lap-weighted. They include all
observations for the driver, including unmatched telemetry laps. Each has an
available sample count and a flagged sample count. Missing values are excluded
from that metric's denominator, not converted to zero. The result gives
recorded/timed laps and missing/unmatched telemetry lap counts.

`analyze_laps` returns original lap rows with `telemetry_missing`,
`timing_incomplete` (missing/nonpositive lap time or sector) and absolute
seconds from the median valid lap time. It returns mean, median, sample standard
deviation and 25/50/75% lap-time quantiles, plus sector means. Fastest/slowest
use positive available lap durations; "most consistent lap" is the individual
lap closest to the driver's median, **not** a measure of race-wide consistency.
Ties choose the first recorded lap. Missing lap numbers are gaps from 1 to the
largest recorded lap only; a retirement or absent final lap cannot be inferred
from this. It does not exclude pit, safety-car, inaccurate or deleted laps.

## Trace alignment and corners

`align_traces` bins each observed `distance` into the half-open interval
`[floor(distance / bin_size_m) * bin_size_m, start + bin_size_m)`. It does not
assume equal timestamps, interpolate, or manufacture samples. `samples`
contains all selected original observations, flags and provenance; out-of-range
or unavailable distances have no bin, remain in `samples`, and are counted in
coverage as `unaligned_samples`. `bins` contains separate driver/lap/bin
arithmetic sample means, available counts and flagged counts for speed,
throttle, brake, RPM and gear; an absent bin is unavailable, not zero. Average
gear is descriptive, not an actual gear state. Means include flagged readings.
Compare bin starts across drivers only where both have observations.

`compare_corners` uses `corners.Distance` and per-lap telemetry `distance` in
metres, assuming the same lap origin and comparable distance scale. For each
requested lap and corner it summarizes observed speed within the inclusive
`Distance ± window_m` interval, without interpolation or wraparound at the
start/finish line. It reports sample counts, available-speed counts, suspicious
sample counts, telemetry source filenames and corner source. No sample gives
null speed, not zero. Upstream distance may be noisy or not perfectly aligned
between drivers and corner metadata; coordinates are not used because their
scale is uncertain. This is a window approximation, not the exact apex speed.

## Quality policy

Per-sample flags use the ingestion screening bounds: speed 0–400 km/h, rpm
0–25,000, gear integer 0–8, throttle 0–100%, brake 0/1, distance 0–10,000 m,
and relative distance 0–1. Missing measurements are not flagged as physical
outliers, and are distinguishable from measured zero by null status. Flagged
values, including throttle overshoots, are **not clipped or discarded** from
metrics. Out-of-range distances remain visible but have no alignment bin;
corner windows include any values within the window and report flags. These
bounds are screens, not proof of validity, and upstream position data and
accelerations may already be interpolated or derived. CSV loading is in-memory
and can require substantial RAM for large races.
