"""Interactive assumption-driven race strategy scenarios."""

from dataclasses import replace

import plotly.graph_objects as go
import streamlit as st

from apexlab.dashboard.helpers import driver_options
from apexlab.dashboard.theme import COLORS, section, style
from apexlab.strategy import construct_stints, fit_stint
from apexlab.strategy.replay import observations_as_of, supported_compounds
from apexlab.strategy.simulator import Assumptions, CompoundPace, compare_scenarios, enumerate_windows, simulate


def render(data, metadata):
    st.caption("SIMULATION / ASSUMPTION-DRIVEN, NOT A HISTORICAL RESULT")
    st.warning("Hypothetical scenarios only. Observational tire trends are confounded, not causal. "
               "No held-out race validation or real-world predictive accuracy is claimed.")
    drivers = driver_options(data)
    if not drivers:
        st.info("No drivers available.")
        return
    driver = st.selectbox("Driver", drivers, key="sim_driver")
    total = metadata.get("data", {}).get("total_laps")
    max_cutoff = int(total) - 3 if isinstance(total, int) and total >= 3 else 497
    max_cutoff = max(0, max_cutoff)
    cutoff = st.number_input("Historical replay cutoff: completed laps", min_value=0, max_value=max_cutoff,
                             value=0, step=1, key="sim_cutoff")
    try:
        history = observations_as_of(data.laps, driver, int(cutoff))
        available = supported_compounds(history)
    except ValueError as exc:
        st.error(f"Replay observations unavailable: {exc}")
        return
    st.caption(f"Only {len(history)} {driver} lap records at or before lap {cutoff} are visible to the simulator. "
               f"Supported observed compounds: {', '.join(available) if available else 'none'}.")
    if not available:
        st.info("Select a cutoff with observed compound data before configuring a simulation.")
        return
    if {"stint", "life", "pin", "pout", "status", "iacc", "ff1G", "del"}.issubset(history.columns):
        try:
            segments, summaries = construct_stints(history)
        except ValueError as exc:
            st.error(f"Observed trend context unavailable: {exc}")
            return
        with st.expander("Observed pre-cutoff trend context (optional, not causal)"):
            st.caption("Eligible laps only: valid reported life and lap time, recorded clear status, "
                       "no recorded pit timestamp, accurate, not generated or deleted. "
                       "The last segment may still be in progress at the cutoff.")
            for item in summaries.to_dict("records"):
                if item["incomplete"] or item["compound_conflict"] or item["tire_life_decreases"]:
                    st.warning(f"Stint {item['source_stint']} has incomplete or inconsistent source data: "
                               f"missing laps {item['missing_lap_numbers']}, "
                               f"compound conflict {item['compound_conflict']}, "
                               f"decreasing reported life {item['tire_life_decreases']}.")
                try:
                    fit = fit_stint(segments[segments["segment_id"] == item["segment_id"]])
                except ValueError as exc:
                    st.caption(f"Stint {item['source_stint']}: {exc}")
                    continue
                st.caption(f"Stint {item['source_stint']} · {item['compound']} · n={fit['n']} · "
                           f"slope {fit['slope_seconds_per_lap']:.4f} s/reported-life lap. "
                           "This is context only; enter any modeling assumption explicitly below.")
    st.markdown("#### Scenario assumptions")
    st.caption("Illustrative zero-adjustment defaults are not inferred from historical pit loss or tire performance. "
               "Review every assumption before running.")
    with st.form("simulation_form"):
        first, second, third = st.columns(3)
        baseline = first.number_input("Baseline pace (s/lap)", min_value=1.0, value=100.0, step=0.1)
        max_distance = min(100, total - int(cutoff)) if isinstance(total, int) and total >= 3 else 100
        distance = second.number_input("Simulation distance (laps)", min_value=3, max_value=max_distance,
                                       value=max_distance, step=1)
        count = third.selectbox("Number of pit stops", [1, 2])
        a, b, c = st.columns(3)
        loss = a.number_input("Assumed pit-lane loss (s/stop)", min_value=0.0, value=0.0, step=0.5)
        starting_age = b.number_input("Starting tire assumed age (laps)", min_value=0, value=0, step=1)
        new_age = c.number_input("Replacement tire assumed age (laps)", min_value=0, value=0, step=1)
        a, b, c = st.columns(3)
        track = a.number_input("Track adjustment (s/lap)", value=0.0, step=0.1)
        noise = b.number_input("Lap uncertainty SD (s)", min_value=0.0, value=0.0, step=0.1)
        seed = c.number_input("Random seed", min_value=0, value=42, step=1)
        compounds = [st.selectbox(f"Stint {i + 1} compound", available, key=f"sim_compound_{i}")
                     for i in range(count + 1)]
        assumptions = {}
        for compound in sorted(set(compounds)):
            a, b = st.columns(2)
            offset = a.number_input(f"{compound} pace offset (s/lap)", value=0.0, step=0.1, key=f"offset_{compound}")
            slope = b.number_input(f"{compound} assumed trend (s/age lap)", value=0.0, step=0.01, key=f"trend_{compound}")
            assumptions[compound] = CompoundPace(offset, slope)
        st.caption("Pit windows are relative remaining-lap numbers; a stop occurs after that lap. "
                   "Each window must end before the final lap.")
        windows = []
        for i in range(count):
            low, high = st.columns(2)
            start = low.number_input(f"Stop {i + 1} window start", min_value=1, max_value=99, value=i + 1, step=1)
            end = high.number_input(f"Stop {i + 1} window end", min_value=1, max_value=99, value=i + 2, step=1)
            windows.append((int(start), int(end)))
        run = st.form_submit_button("Compare scenarios")
    if not run:
        return
    if isinstance(total, int) and int(distance) != total - int(cutoff):
        st.info("This is a partial remaining-race horizon, not a prediction to the race finish.")
    settings = Assumptions(baseline, assumptions, loss, int(starting_age), int(new_age), track, noise, int(seed))
    try:
        choices = enumerate_windows(int(distance), windows, compounds, settings, available)
        earliest = min(choices["pit_laps"])
        latest = max(choices["pit_laps"])
        best = choices.iloc[0]["pit_laps"]
        scenarios = [(name, simulate(int(distance), pits, compounds, settings, available))
                     for name, pits in (("Early", earliest), ("Late", latest), ("Best tested", best))]
        baseline_result = simulate(int(distance), (), [compounds[0]], settings, available)
        scenarios.insert(0, ("No-stop baseline", baseline_result))
        if count == 2:
            one = simulate(int(distance), (best[0],), compounds[:2], settings, available)
            scenarios.append(("One-stop reference", one))
        else:
            st.caption("Select two stops to compare against a one-stop reference.")
        table = compare_scenarios(scenarios)
    except ValueError as exc:
        st.error(f"Cannot simulate: {exc}")
        return
    section("Scenario comparison / simulation horizon")
    st.success(f"Best tested pit lap(s): {best}; deterministic predicted remaining time "
               f"{choices.iloc[0]['total_seconds']:.2f} s.")
    st.dataframe(table, hide_index=True, width="stretch")
    fig = go.Figure(go.Bar(x=table["scenario"], y=table["delta_seconds"], marker_color=COLORS[0],
                           hovertemplate="%{x}<br>%{y:+.2f} s vs no-stop<extra></extra>"))
    st.plotly_chart(style(fig, "Predicted difference / no-stop baseline", "", "Seconds", 290), width="stretch")
    window_fig = go.Figure(go.Scatter(
        x=[", ".join(str(lap) for lap in pits) for pits in choices["pit_laps"]],
        y=choices["total_seconds"], mode="markers", marker={"color": COLORS[1], "size": 7},
        hovertemplate="Stop lap(s): %{x}<br>%{y:.2f} s<extra></extra>"))
    st.plotly_chart(style(window_fig, "Tested pit windows", "Relative stop lap(s)", "Predicted time (s)", 300),
                    width="stretch")
    section("Sensitivity / best tested strategy")
    sensitivities = []
    for label, assumption in (
        ("Configured", settings),
        ("Pit loss +1 s", replace(settings, pit_loss_seconds=loss + 1)),
        ("All trends +0.01 s/lap", replace(settings, compound_pace={
            name: replace(value, trend_seconds_per_lap=value.trend_seconds_per_lap + .01)
            for name, value in assumptions.items()})),
        ("Lap uncertainty +0.5 s SD", replace(settings, lap_noise_std_seconds=noise + .5)),
    ):
        result = simulate(int(distance), best, compounds, assumption, available)
        sensitivities.append((label, result))
    st.dataframe(compare_scenarios(sensitivities), hide_index=True, width="stretch")
    st.caption("Intervals are simulated 5th–95th percentiles under independent normal lap noise; "
               "1,000 draws use the selected seed. Noise may produce physically implausible lap times at large SD. "
               "Window optimum minimizes deterministic mean, not risk. Pit loss excludes modeling traffic, fuel, "
               "weather transitions or competition; these inputs are assumptions, not fitted historical facts.")
