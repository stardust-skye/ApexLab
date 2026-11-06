import plotly.graph_objects as go
import streamlit as st

from apexlab.analytics import analyze_laps
from apexlab.dashboard.helpers import driver_options, format_value
from apexlab.dashboard.theme import COLORS, section, style


def render(data):
    st.caption("TIMING ANALYSIS  /  LAP AND SECTOR PERFORMANCE")
    drivers = driver_options(data)
    if not drivers:
        st.warning("No drivers available.")
        return
    driver = st.selectbox("Driver", drivers, key="lap_driver")
    if data.laps.loc[data.laps["drv"] == driver].empty:
        st.info("No recorded laps for this driver.")
        return
    analysis = analyze_laps(data, driver)
    laps = analysis["laps"].sort_values("lap")
    cols = st.columns(4)
    cols[0].metric("FASTEST LAP", str(analysis["fastest_lap"] or "Unavailable"))
    cols[1].metric("SLOWEST LAP", str(analysis["slowest_lap"] or "Unavailable"))
    cols[2].metric("MEDIAN", format_value(analysis["median_seconds"], " s", 3))
    cols[3].metric("CONSISTENCY · SD", format_value(analysis["std_seconds"], " s", 3))
    section("Timing / progression and distribution")
    left, right = st.columns([1.5, 1])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=laps["lap"], y=laps["time"].where(laps["time"] > 0),
                             mode="markers", name="Lap time", marker_color=COLORS[0], connectgaps=False,
                             hovertemplate="Lap %{x}<br>%{y:.3f} s<extra></extra>"))
    left.plotly_chart(style(fig, "Lap-time progression", "Lap", "Seconds"), width="stretch")
    fig = go.Figure(go.Histogram(x=laps["time"].where(laps["time"] > 0), name=driver, marker_color=COLORS[1]))
    right.plotly_chart(style(fig, "Lap-time distribution", "Seconds", "Laps"), width="stretch")
    section("Sector timing / lap-by-lap")
    fig = go.Figure()
    for index, field in enumerate(("s1", "s2", "s3")):
        fig.add_trace(go.Scatter(x=laps["lap"], y=laps[field].where(laps[field] > 0),
                                 mode="markers", name=field.upper(), marker_color=COLORS[index], connectgaps=False,
                                 hovertemplate="Lap %{x}<br>%{y:.3f} s<extra>%{fullData.name}</extra>"))
    st.plotly_chart(style(fig, "Sector times", "Lap", "Seconds"), width="stretch")
    st.caption("Positive available times only; no pit, safety-car or deleted-lap filtering. SD is sample standard deviation; "
               "the closest-to-median lap is not a measure of race-wide consistency.")
    with st.expander(f"Lap records / {int(laps['timing_incomplete'].sum())} incomplete, {int(laps['telemetry_missing'].sum())} missing telemetry"):
        st.dataframe(laps[["lap", "time", "s1", "s2", "s3", "timing_incomplete", "telemetry_missing", "source_file", "source_row"]],
                     hide_index=True, width="stretch")
    st.write(f"Closest to median: lap {analysis['most_consistent_lap'] or 'unavailable'} · "
             f"Missing lap numbers within recorded range: {analysis['missing_lap_numbers_within_recorded_range']}")
