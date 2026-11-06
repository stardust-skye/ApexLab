# United States Grand Prix Race: inspected schema

This describes the snapshot at commit
`9012398e92459a7cb1e3cbe06bee1b962e1c495b`, not a guarantee about other
sessions. See the upstream [data reference](https://github.com/TracingInsights/2026/blob/9012398e92459a7cb1e3cbe06bee1b962e1c495b/DATA_REFERENCE.md)
for definitions and caveats. All six session JSON files and all 1,165 telemetry
files were profiled; individual telemetry samples were inspected for VER, NOR,
HAM and BOT.

## Representation and provenance

The session tables other than drivers are JSON objects of parallel arrays.
Each telemetry file has an object `tel` with parallel arrays and scalar
`dataKey`. Drivers are in a `drivers` array of objects. `corners.json` contains
several independent arrays with different lengths: 20 corners, 12 sections,
20 marshal lights, 20 marshal sectors, 853 track coordinates and 21 mini-sector
indices. Equal lengths do **not** imply that marshal records align with corners.

The source uses both JSON null and the **string** `"None"` for missing values;
the latter appears in numerical, boolean and string fields. In CSV both become
`\N`; unalignable arrays are also represented as `\N` and reported separately.
Empty strings remain empty. For pandas reading, use
`pd.read_csv(path, keep_default_na=False, na_values=["\\N"], dtype={...})`;
specify string types for identifiers, codes and mini-sectors to preserve leading
zeroes. CSV otherwise has no intrinsic schema.

Every row includes race-relative `source_file` and zero-based `source_row`.
Telemetry also includes driver and lap from its path and its source `dataKey`.
No missing laps or sensor observations are synthesized. Times and fields retain
their original names, units and values; no timestamps are inferred.

## Session data

- **drivers.json**: `drivers` (22 objects); `driver` (three-letter string),
  `team` (string), `dn` (driver-number string), `fn`, `ln`, `tc` (hex team
  colour), and `url` (string). The drivers table adds provenance.
- **session_laptimes.json**: 1,165 records; all keys are arrays. `drv`, `dNum`
  are strings; `lap`, `stint`, `life`, `pos` are integers where available.
  `time`, `s1`, `s2`, `s3` are lap/sector durations in seconds; `sesT`, `lST`,
  `pout`, `pin`, `s1T`, `s2T`, `s3T` are session-relative seconds.
  `lSD` is an ISO 8601 lap-start timestamp with nanosecond fractional seconds,
  without an explicit offset; upstream describes it as UTC. `vi1`, `vi2`,
  `vfl`, `vst` are speeds in km/h. `compound`, `team`, `status`, `delR` and
  `ms1`/`ms2`/`ms3` are strings (mini-sectors are digit codes, not numbers).
  `pb`, `fresh`, `del`, `ff1G`, `iacc` are booleans. `wT`, `wAT`, `wH`,
  `wP`, `wR`, `wTT`, `wWD`, `wWS` are lap-associated weather as described
  below. Some lap timing, tyre life, position, boolean and pit fields use
  `"None"`, notably 2 lap durations and 24 first-sector times.
- **weather.json**: 159 parallel records. `wT` is session-relative seconds;
  `wAT`/`wTT` air/track temperature in °C, `wH` humidity percent, `wP`
  pressure mbar, `wR` boolean rainfall, `wWD` wind direction degrees and `wWS`
  wind speed m/s. Numeric fields are integers or floats.
- **rcm.json**: 171 parallel records. `time` is an ISO 8601 timestamp with
  nine fractional digits and no offset (upstream UTC); `cat`, `msg`, `status`,
  `flag`, `scope`, `dNum` are strings; `sector` is a float or `"None"`, `lap`
  an integer. Optional status/flag/scope/sector/driver are often `"None"`.
- **session_info.json**: `t0_date` is an ISO 8601 UTC time-zero string without
  offset; `session_start_time` is seconds relative to that zero; `total_laps`
  is an integer; `track_status` and `session_status` contain parallel `Time`
  (seconds) and `Status` arrays, with `Message` for track status. Nested
  `session_info` includes meeting/circuit metadata, `StartDate`/`EndDate`
  as local ISO strings and `GmtOffset` as signed hours:minutes:seconds.
  These nested data are preserved in `session_metadata.json`, not flattened
  into the six analytical tables.
- **corners.json**: corner-level `CornerNumber` (integer), `CornerLetter`,
  `CornerLabel`, `Section` (strings), `X`, `Y`, `Angle`, `Distance`, `MVDistance`
  (floats). Distances are metres, angles degrees. Upstream describes the
  position coordinates as track coordinates; verify its scaling before
  converting to physical metres. Scalar circuit/layout metadata and the
  independent `Section*`, `MarshalLight*`, `MarshalSector*`, `Track*` and
  `MiniSectorIndex` arrays remain in `circuit_metadata.json`; they are not
  incorrectly joined by ordinal position.

## Telemetry

In the 1,165 files, `tel.time` is floating-point seconds since the start of
that lap. `rpm` is engine rpm, `speed` km/h, `gear` integer 0–8, `throttle`
percent, `brake` and `drs` integer binary flags. `distance` and
`DistanceToDriverAhead` are metres; `rel_distance` is unitless;
`DriverAhead` is a driver-number string. `acc_x`, `acc_y`, `acc_z` are
derived accelerations in m/s², **not raw IMU measurements**. `x`, `y`, `z`
are interpolated positional coordinates; their physical scale should be
verified before use. `dataKey` is a driver/lap identifier string. Sampling is
irregular and these upstream fields include interpolated and derived values.

`BOT/51_tel.json` has three time samples but nine each of `acc_y` and `acc_z`.
Those two arrays cannot be aligned to the three samples without an assumption;
the output retains all three samples but leaves both fields null and reports
the mismatch. The original arrays remain in raw data. `BOT/50_tel.json` is
absent, while `BOT/51_tel.json` has no matching session lap.

## Validation scope

The report counts duplicate natural keys, invalid absolute and relative times,
missing driver references, invalid lap numbers, nulls in essential fields and
telemetry outside screening bounds. Bounds are speed 0–400 km/h, rpm
0–25,000, gear 0–8, throttle 0–100%, brake/DRS 0 or 1, distance 0–10,000 m,
relative distance 0–1, distance ahead 0–10,000 m and derived acceleration
-150 to 150 m/s². These deliberately broad thresholds are not a physical
certification, and even small interpolation overshoots are reported rather than
corrected. The JSON report includes counts for every column, up to 10 examples
for each check, all coverage gaps and each unaligned array. Unreported rules
had zero findings. Manifest coverage compares filenames, not file hashes.
