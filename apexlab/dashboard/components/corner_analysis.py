import plotly.graph_objects as go
import streamlit as st

from apexlab.analytics import align_traces, compare_corners
from apexlab.dashboard.components.common import lap_select, plot_bins
from apexlab.dashboard.helpers import driver_options, prepare_trace_bins
from apexlab.dashboard.theme import COLORS, section, style


def render(data):
    st.caption("CIRCUIT ANALYSIS  /  CORNER WINDOW")
    options = driver_options(data)
    if len(options) < 2:
        st.warning("At least two drivers are required for corner comparison.")
        return
    drivers = st.multiselect("Drivers", options, default=options[:2], key="corner_drivers")
    if len(drivers) < 2:
        st.info("Select at least two drivers.")
        return
    lap = lap_select(data, drivers, "corner")
    if lap is None:
        return
    if data.corners.empty:
        st.info("No corner metadata is available.")
        return
    corners = data.corners.reset_index(drop=True)
    index = st.selectbox("Circuit corner", list(corners.index),
                         format_func=lambda i: str(corners.loc[i].get("CornerLabel", corners.loc[i, "CornerNumber"])),
                         key="corner_index")
    corner = corners.loc[index]
    window = st.slider("Window either side of corner (m)", 25, 200, 50, 25)
    selections = [(driver, int(lap)) for driver in drivers]
    summary = compare_corners(data, selections, window_m=window)
    selected = summary.loc[(summary["CornerNumber"] == corner["CornerNumber"])
                           & (summary["CornerLetter"].fillna("") == (corner["CornerLetter"] or ""))]
    section("Corner speed / observed window")
    for row in selected.to_dict("records"):
        if not row["telemetry_available"]:
            st.warning(f"{row['driver']} lap {lap}: telemetry unavailable.")
        elif not row["samples_in_window"]:
            st.info(f"{row['driver']} lap {lap}: no observations in this corner window.")
    fig = go.Figure(go.Bar(x=selected["driver"], y=selected["speed_mean_kmh_sample"],
                           marker_color=[COLORS[drivers.index(driver) % len(COLORS)] for driver in selected["driver"]],
                           customdata=selected[["speed_available_samples", "speed_flagged_samples"]],
                           hovertemplate="%{x}<br>Mean %{y:.1f} km/h<br>Samples %{customdata[0]}<br>Flagged %{customdata[1]}<extra></extra>"))
    st.plotly_chart(style(fig, "Mean observed speed in window", "", "km/h", 280), width="stretch")
    with st.expander("Corner comparison / coverage and provenance"):
        st.dataframe(selected, hide_index=True, width="stretch")
    aligned = align_traces(data, selections)
    bins = prepare_trace_bins(aligned, selections, ["Speed"])
    distance = float(corner["Distance"])
    near = bins.loc[bins["distance_bin_start_m"].between(distance - window - aligned["bin_size_m"], distance + window)]
    if not near.empty:
        plot_bins(near, selections, "speed", "km/h", "Nearby speed observations · 25 m bins")
    samples = aligned["samples"]
    points = samples.loc[samples["distance"].between(distance - window, distance + window),
                         ["driver", "lap", "time", "distance", "speed", "flag_distance", "flag_speed",
                          "source_file", "source_row"]]
    with st.expander("Observed distances and speeds in the exact window"):
        st.dataframe(points, hide_index=True, width="stretch")
    st.caption(f"Corner distance {distance:.1f} m. Windows assume telemetry and corner distances share an origin and scale; "
               "bins can overlap the window edge. No start/finish wraparound, interpolation or exact apex measurement.")
