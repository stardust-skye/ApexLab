import streamlit as st
import plotly.graph_objects as go

from apexlab.analytics import analyze_laps, compare_drivers
from apexlab.dashboard.components.common import pair_select
from apexlab.dashboard.helpers import format_value
from apexlab.dashboard.theme import COLORS, section, style


def render(data):
    st.caption("HEAD TO HEAD  /  SESSION-WIDE PERFORMANCE")
    drivers = pair_select(data, "comparison")
    if not drivers:
        return
    result = compare_drivers(data, drivers).set_index("driver")
    labels = {
        "speed_mean_kmh_sample": "Mean speed · km/h",
        "speed_max_kmh_sample": "Maximum speed · km/h",
        "lap_mean_seconds": "Mean lap time · s",
        "lap_std_seconds": "Lap time consistency (sample SD) · s",
        "throttle_mean_pct_sample": "Mean throttle · %",
        "brake_active_fraction_sample": "Brake-active sample fraction",
        "timed_laps": "Timed laps",
        "telemetry_samples": "Telemetry samples",
        "throttle_flagged_samples": "Flagged throttle samples",
        "missing_telemetry_laps": "Missing telemetry laps",
    }
    section("Performance / driver profiles")
    columns = st.columns(2)
    for index, driver in enumerate(drivers):
        with columns[index]:
            st.markdown(f"### {driver}")
            row = result.loc[driver]
            a, b = st.columns(2)
            a.metric("MEAN SPEED", format_value(row["speed_mean_kmh_sample"], " km/h"))
            b.metric("MAX SPEED", format_value(row["speed_max_kmh_sample"], " km/h"))
            a.metric("MEAN LAP", format_value(row["lap_mean_seconds"], " s", 3))
            b.metric("LAP SD", format_value(row["lap_std_seconds"], " s", 3))
            a.metric("THROTTLE MEAN", format_value(row["throttle_mean_pct_sample"], " %"))
            b.metric("BRAKE FRACTION", format_value(row["brake_active_fraction_sample"], "", 3))
    section("Lap timing / comparison")
    fig = go.Figure()
    for index, driver in enumerate(drivers):
        if data.laps.loc[data.laps["drv"] == driver].empty:
            continue
        laps = analyze_laps(data, driver)["laps"].sort_values("lap")
        fig.add_trace(go.Scatter(x=laps["lap"], y=laps["time"].where(laps["time"] > 0),
            mode="markers", marker={"size": 6, "color": COLORS[index]}, name=driver,
            hovertemplate="Lap %{x}<br>%{y:.3f} s<extra>%{fullData.name}</extra>"))
    st.plotly_chart(style(fig, "Lap-time progression", "Lap", "Lap time (s)", 310), width="stretch")
    section("Sector performance / mean seconds")
    fig = go.Figure()
    for index, driver in enumerate(drivers):
        fig.add_trace(go.Bar(name=driver, x=["Sector 1", "Sector 2", "Sector 3"],
            y=[result.loc[driver, f"s{n}_mean_seconds"] for n in (1, 2, 3)],
            marker_color=COLORS[index], hovertemplate="%{x}<br>%{y:.3f} s<extra>%{fullData.name}</extra>"))
    fig.update_layout(barmode="group")
    st.plotly_chart(style(fig, "Mean available sector times", "", "Seconds", 280), width="stretch")
    with st.expander("Full metric breakdown"):
        st.dataframe(result[list(labels)].rename(columns=labels).T, width="stretch")
    st.caption("Speed, throttle and brake are sample-weighted, not time-weighted; lap mean and sample SD "
               "use positive available lap times. Null means unavailable, not zero. Flagged readings remain included.")
