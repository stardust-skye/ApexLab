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

## Assumption-driven strategy simulator

The source provides pit-in/out timestamps, compound, source stint and reported
tire life, lap and sector times, weather and track status as audited above.
Pit timestamps alone do not measure net pit loss against an unimpeded lap.
The source circuit metadata also reports `PitLossNormal=20.81`,
`PitLossSC=13.5` and `PitLossVSC=14.34` seconds; these are upstream metadata,
not established measured historical losses. The simulator does not use them
automatically. It does not derive compound offsets, fuel effects, traffic,
future weather, or causal tire wear from the source. User-entered values are
scenario assumptions, including the illustrative UI defaults.

Select a driver and a **completed-lap cutoff**. `observations_as_of` first
restricts that driver's observations to laps at or before the cutoff; only
then are compound labels collected or source stint trends calculated. Invalid
source lap identifiers fail validation, because their ordering is unknowable.
The session's scheduled race length is treated as known metadata, not a
future lap observation. The optional pre-cutoff trend is displayed as
observational context only; it is not inserted into the simulator. The user
must explicitly set the baseline, per-compound offsets and trends, initial and
replacement tire ages, pit loss, track adjustment and uncertainty. Actual
reported life is not silently converted to a start-of-lap age. Selectable
compound labels must have been observed for that driver by the cutoff; this
does not establish tire-set availability or a legal future strategy.

The simulation runs for a chosen remaining-lap horizon. If that is shorter
than scheduled distance minus cutoff, it is explicitly a partial horizon.
Laps are numbered relative to the simulation start. A pit occurs **after**
its specified lap; its fixed loss is charged once on that lap, and the next
lap starts with the assumed replacement tire age. Initial age and replacement
age are simulation conventions, not claims about the source's `life` field.
For each lap, in seconds:

```
pace = baseline + compound_offset + compound_trend * assumed_age + track_adjustment
lap_time = pace + (pit_loss if stopping after this lap else 0)
total = sum(lap_time)
```

Zero-, one-, and two-stop schedules are supported; zero stops is the
constant-policy comparison baseline, not a claim that it is legal. The UI
compares early, late and best tested plans against it, plus a one-stop
reference when two stops are selected. Stop laps must be distinct, increasing,
at least 1 and strictly before the last simulated lap; each stint has at
least one lap. Inclusive windows must obey these limits and contain a feasible
schedule. At most 5,000 window combinations are enumerated. The reported
optimum minimizes deterministic expected time **within the tested windows
and selected compound sequence**, not over all possible race strategies.
Lap pace must remain positive. No sporting tire-compound rules, tire-set
inventories, traffic, competitors, fuel dynamics, time-varying weather or
safety-car pit-loss dynamics are simulated.

Optional uncertainty is independent Gaussian noise with user-specified per-lap
standard deviation, summed over the horizon with a fixed seed. The 5th–95th
percentiles are scenario-draw intervals, not a confidence interval or a
calibrated prediction interval. Normal draws are unbounded and can imply
implausible lap times at high noise; values are not clipped. Sensitivity fixes
the chosen strategy and reports changes for pit loss +1 second, all compound
trends +0.01 s/age-lap, and uncertainty +0.5 s/lap. These do not re-optimize
the strategy. None of these evaluations demonstrates real-world accuracy;
held-out multi-race validation is still required.

```python
from apexlab.strategy.simulator import Assumptions, CompoundPace, enumerate_windows, simulate

settings = Assumptions(
    baseline_seconds=100, compound_pace={"SOFT": CompoundPace(0, .2)},
    pit_loss_seconds=20, starting_age=0, new_tire_age=0,
    track_adjustment_seconds=0, lap_noise_std_seconds=0, seed=42, draws=1000,
)
supported = ["SOFT"]  # Obtain from supported_compounds(observations_as_of(...)).
best = enumerate_windows(10, [(2, 8)], ["SOFT", "SOFT"], settings, supported)
scenario = simulate(10, (5,), ["SOFT", "SOFT"], settings, supported)
print(best.iloc[0]["pit_laps"], scenario["total_seconds"])  # (5,), 1024.0
```

In this synthetic example, the same assumptions yield 1,025.8 s for a stop
after lap 2, 1,024.0 s after lap 5, 1,042.4 s for stops after laps 3 and 7,
and 1,009.0 s without stopping. These are mathematical checks, not predictions
of a real race. Tests cover pit-loss accounting, age resets, window constraints,
distance, seeded uncertainty, replay cutoff and baseline comparisons.
