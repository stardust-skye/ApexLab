"""Tire and stint research workspace."""

import pandas as pd
import streamlit as st

from apexlab.dashboard.helpers import driver_options, format_value
from apexlab.dashboard.theme import section
from apexlab.strategy import construct_stints, evaluate_holdout, fit_stint
from apexlab.strategy.charts import lap_progression, life_trend, residual_uncertainty


def render(data):
    st.caption("OBSERVATIONAL RESEARCH / SOURCE-REPORTED TIRE STINTS")
    st.warning("Lap-time trends are not causal tire degradation. Fuel, traffic, track evolution, weather and driver changes remain confounded.")
    try:
        laps, stints = construct_stints(data.laps)
    except ValueError as exc:
        st.error(f"Stint analysis unavailable: {exc}")
        return
    drivers = [d for d in driver_options(data) if (laps["drv"] == d).any()]
    if not drivers:
        st.info("No source laps available.")
        return
    driver = st.selectbox("Driver", drivers, key="tire_driver")
    driver_laps = laps[laps["drv"] == driver]
    choices = stints.loc[stints["driver"] == driver]
    section("Stint progression / recorded observations")
    st.plotly_chart(lap_progression(driver_laps), width="stretch")
    if choices.empty:
        st.info("No source-reported stint segments.")
        return
    segment = st.selectbox("Stint", choices["segment_id"].tolist(),
                           format_func=lambda value: f"Stint {choices.set_index('segment_id').loc[value, 'source_stint']} · laps {choices.set_index('segment_id').loc[value, 'first_lap']}–{choices.set_index('segment_id').loc[value, 'last_lap']}",
                           key="tire_stint")
    info = choices.set_index("segment_id").loc[segment]
    selected = driver_laps[driver_laps["segment_id"] == segment]
    a, b, c, d = st.columns(4)
    a.metric("COMPOUND", info["compound"] if pd.notna(info["compound"]) else "Unavailable")
    b.metric("RECORDED LAPS", int(info["recorded_laps"]))
    c.metric("MODEL-ELIGIBLE", int(info["eligible_laps"]))
    d.metric("SOURCE STINT", str(info["source_stint"]) if pd.notna(info["source_stint"]) else "Unavailable")
    if info["incomplete"] or info["compound_conflict"] or info["tire_life_decreases"]:
        st.warning(f"Incomplete or inconsistent stint: missing lap numbers {info['missing_lap_numbers']}; "
                   f"compound conflict: {info['compound_conflict']}; life decreases: {info['tire_life_decreases']}. "
                   "Source stint boundaries may be uncertain.")
    if not info["pit_entry_observed"] and not info["pit_exit_observed"]:
        st.caption("No pit timestamp observed within this segment; the recorded stint number is not independently verified.")
    if info["stint_evidence"] != "source-reported" or pd.isna(info["compound"]):
        st.warning("Source stint or compound unavailable; no tire trend will be fitted.")
        fitted = None
    else:
        try:
            fitted = fit_stint(selected)
        except ValueError as exc:
            fitted = None
            st.info(str(exc))
    section("Lap time / reported tire life")
    st.caption("Reported life is not asserted to be tire age at lap start. Excludes pit, non-green, inaccurate, deleted and generated laps from the fit.")
    st.plotly_chart(life_trend(selected, fitted), width="stretch")
    if fitted:
        a, b, c = st.columns(3)
        a.metric("OLS TREND", format_value(fitted["slope_seconds_per_lap"], " s/lap", 3))
        low, high = fitted["slope_interval_95"]
        b.metric("95% BOOTSTRAP", f"{low:.3f} to {high:.3f} s/lap")
        c.metric("TRAIN RMSE", format_value(fitted["training_rmse_seconds"], " s", 3))
        st.caption("Descriptive pairs bootstrap assumes exchangeable observations; serial correlation and confounding can invalidate coverage. Not a causal or prediction interval.")
        st.caption(f"Robust median pairwise slope: {fitted['median_pairwise_slope_seconds_per_lap']:.3f} s/lap. "
                   "This diagnostic does not remove confounding.")
        st.plotly_chart(residual_uncertainty(fitted), width="stretch")
        with st.expander("Residual and outlier diagnostics"):
            st.dataframe(fitted["observations"][["lap", "reported_tire_life", "time", "fitted_seconds",
                         "residual_seconds", "residual_outlier", "source_file", "source_row"]], hide_index=True)
        peers = choices[(choices["segment_id"] != segment) & (choices["compound"] == info["compound"])]
        if not peers.empty:
            peer = st.selectbox("Holdout stint (same driver and compound)", peers["segment_id"].tolist(),
                                format_func=lambda value: f"Stint {choices.set_index('segment_id').loc[value, 'source_stint']}",
                                key="tire_holdout")
            try:
                result = evaluate_holdout(selected, driver_laps[driver_laps["segment_id"] == peer])
                st.write(f"Held-out {result['validation_n']} laps · trend RMSE {result['trend_rmse_seconds']:.3f} s · "
                         f"constant-pace RMSE {result['constant_rmse_seconds']:.3f} s. Single held-out stint, not a general performance claim.")
            except ValueError as exc:
                st.info(f"Holdout comparison unavailable: {exc}")
        else:
            st.info("No other same-compound stint for this driver; held-out evaluation unavailable.")
    with st.expander("Source observations and inclusion flags"):
        st.dataframe(selected[["lap", "source_stint", "compound", "life", "pin", "pout", "status",
                               "time", "eligible", "source_file", "source_row"]], hide_index=True)
