# Tire and stint research

## Availability audit

The 2026 United States Race source `session_laptimes.json` provides driver,
lap, source stint number, compound, `life` (reported tire life), `fresh`,
pit-in/out timestamps, lap/sector times, track status and lap-associated
weather. The processed table preserves them and provenance. All 1,165 laps
have a source stint and compound (SOFT 456, MEDIUM 203, HARD 506); 26 have
missing reported tire life. Lap-time is missing twice; pit timestamps are
sparse (34 in, 33 out). Track status and weather are present. The independent
weather, race-control and session-state data add context. Reference:
[TracingInsights DATA_REFERENCE.md](https://github.com/TracingInsights/2026/blob/9012398e92459a7cb1e3cbe06bee1b962e1c495b/DATA_REFERENCE.md).
The reference defines `life` as laps driven on the tire, including previous
sessions, but does not establish whether the recorded number denotes the
beginning or end of the lap. This code therefore **does not claim start-of-lap
age or subtract one**.

The data supports exploratory associations between recorded tire life and lap
time, not identification of causal tire degradation. Fuel load, evolving track
grip, traffic and clean-air exposure are not directly measured as confounder
controls. Weather and track-status proxies do not solve the causal problem.
Future work needs tire-set identity and explicit age convention, fuel quantities,
traffic/clean-air indicators, track evolution and richer race/stint samples.
There is one race, so cross-race generalization is not testable.

## Stints and model

`construct_stints(laps)` partitions each driver's ordered laps on changes in
the **source-reported** stint number, including same-compound pit stops.
Missing stint numbers are not inferred. It reports evidence of a pit timestamp
at adjacent boundaries, internal missing laps, missing tire life, inconsistent
compound or decreasing tire life; a source stint number is not independent
proof that a tire change occurred. Source file and row are retained. The final
observed lap is not automatically a completed stint: retirement, session end,
or missing later records cannot be distinguished from these fields alone.

The default model sample requires finite positive lap time, nonnegative
integer reported tire life, source status exactly `1` (clear), no recorded
pit-in/out timestamp, `iacc=True`, `ff1G=False`, and `del=False`. Unknown flags
are excluded, not treated as false. Yellow flags, safety-car and VSC phases
are conservatively excluded by the exact status check. Pit timestamp null is
the source's absence of a recorded event, not proof of no pit stop. No data are
filled or deleted; excluded laps remain visible with provenance.

`fit_stint` fits ordinary least squares (seconds vs reported-life laps) to a
single source stint with one known compound, at least five eligible samples
and three distinct ages. The slope is an **observational pace trend**, not a
causal wear rate. It also reports median pairwise slope (robust diagnostic),
residuals, MAD-based outlier flags, and in-sample RMSE against a fitted
constant mean. No automatic outlier removal is done. A 95% pairs bootstrap
interval uses 2,000 resamples and seed 42. It assumes exchangeable observations;
serial correlation, small samples, selection and confounding may make it
poorly calibrated. It is not a prediction interval or a causal confidence
interval.

`evaluate_holdout(train, validation)` compares the frozen training-stint
linear model to its frozen training mean on a **different source stint** for
the same driver and compound. Overlapping driver/lap records are rejected.
Both scores are held-out RMSE in seconds; no random lap-level split occurs.
Each evaluation is a single holdout, subject to different conditions and
extrapolation. Do not claim general predictive improvement from a single
result. Different drivers or compounds require independent comparisons and
are not pooled.

```python
from apexlab.analytics import load_race
from apexlab.strategy import construct_stints, fit_stint, evaluate_holdout
from apexlab.strategy.charts import lap_progression, life_trend, residual_uncertainty

race = load_race()
laps, stints = construct_stints(race.laps)
driver_laps = laps[laps["drv"] == "ALB"]
first = driver_laps[driver_laps["segment_id"] == 1]
fit = fit_stint(first)
print(fit["slope_seconds_per_lap"], fit["slope_interval_95"])
fig = life_trend(first, fit)
```

The dashboard's **Tire & Stint Analysis** provides selection, comparison,
diagnostics and same-driver/same-compound holdout when available. Run
`python -m streamlit run apexlab\dashboard\app.py`.
