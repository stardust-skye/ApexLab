import plotly.graph_objects as go
import streamlit as st

from apexlab.dashboard.helpers import driver_options, lap_options
from apexlab.dashboard.theme import COLORS, style


def pair_select(data, key):
    drivers = driver_options(data)
    if len(drivers) < 2:
        st.warning("At least two drivers are required for comparison.")
        return None
    a, b = st.columns(2)
    first = a.selectbox("Driver A", drivers, key=f"{key}_a")
    remaining = [driver for driver in drivers if driver != first]
    second = b.selectbox("Driver B", remaining, key=f"{key}_b")
    return first, second


def lap_select(data, drivers, key):
    laps = lap_options(data, drivers)
    if not laps:
        st.warning("No recorded or telemetry laps are available for this selection.")
        return None
    return st.selectbox("Lap number", laps, key=f"{key}_lap")


def plot_bins(bins, selections, channel, unit, title):
    fig = go.Figure()
    for index, (driver, lap) in enumerate(selections):
        frame = bins.loc[(bins["driver"] == driver) & (bins["lap"] == lap)]
        fig.add_trace(go.Scattergl(
            x=frame["distance_bin_start_m"], y=frame[f"{channel}_mean"],
            mode="markers", marker={"size": 6, "color": COLORS[index % len(COLORS)]},
            name=f"{driver} · L{lap}", connectgaps=False,
            customdata=frame[[f"{channel}_available_samples", f"{channel}_flagged_samples"]],
            hovertemplate=f"Distance bin %{{x:.0f}} m<br>{title} %{{y:.2f}} {unit}<br>Samples %{{customdata[0]}}<br>Flagged %{{customdata[1]}}<extra>%{{fullData.name}}</extra>",
        ))
    style(fig, title, "Distance bin start (m)", unit, 340)
    st.plotly_chart(fig, width="stretch")
