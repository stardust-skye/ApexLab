import streamlit as st

from apexlab.analytics import align_traces
from apexlab.dashboard.components.common import lap_select, pair_select
from apexlab.dashboard.helpers import CHANNELS, prepare_trace_bins
from apexlab.dashboard.theme import COLORS, section, style
from plotly.subplots import make_subplots
import plotly.graph_objects as go


def render(data):
    st.caption("DISTANCE ALIGNMENT  /  DRIVER TELEMETRY")
    drivers = pair_select(data, "telemetry")
    if not drivers:
        return
    lap = lap_select(data, drivers, "telemetry")
    if lap is None:
        return
    channels = st.multiselect("Channels", list(CHANNELS), default=list(CHANNELS))
    if not channels:
        st.info("Select at least one channel.")
        return
    selections = [(driver, int(lap)) for driver in drivers]
    aligned = align_traces(data, selections)
    for row in aligned["coverage"].to_dict("records"):
        if not row["telemetry_available"]:
            st.warning(f"{row['driver']} lap {row['lap']}: telemetry unavailable.")
        elif not row["timing_available"]:
            st.warning(f"{row['driver']} lap {row['lap']}: telemetry exists without lap timing.")
        if row["unaligned_samples"]:
            st.warning(f"{row['driver']} lap {row['lap']}: {row['unaligned_samples']} samples have no valid distance bin; retained in source.")
    bins = prepare_trace_bins(aligned, selections, channels)
    st.caption("25 m distance bins · sample means · markers only, no interpolation. Missing bins remain absent; "
               "flagged values are included and counted in hover details.")
    with st.expander("Inspect selected source observations and flags"):
        columns = ["driver", "lap", "time", "distance", "flag_distance", "speed", "throttle", "brake",
                   "rpm", "gear", "flag_speed", "flag_throttle", "flag_brake", "flag_rpm", "flag_gear",
                   "source_file", "source_row"]
        st.dataframe(aligned["samples"][columns], hide_index=True, width="stretch")
    if bins.empty:
        st.info("No alignable telemetry samples for this lap.")
        return
    section("Aligned channels / distance domain")
    fig = make_subplots(rows=len(channels), cols=1, shared_xaxes=True, vertical_spacing=.025)
    for row_index, label in enumerate(channels, 1):
        column, unit = CHANNELS[label]
        for index, (driver, lap_number) in enumerate(selections):
            frame = bins.loc[(bins["driver"] == driver) & (bins["lap"] == lap_number)]
            fig.add_trace(go.Scattergl(
                x=frame["distance_bin_start_m"], y=frame[f"{column}_mean"],
                mode="markers", marker={"size": 5, "color": COLORS[index]}, name=driver,
                legendgroup=driver, showlegend=row_index == 1, connectgaps=False,
                customdata=frame[[f"{column}_available_samples", f"{column}_flagged_samples"]],
                hovertemplate=f"Bin %{{x:.0f}} m<br>{label} %{{y:.2f}} {unit}<br>"
                              "Samples %{customdata[0]}<br>Flagged %{customdata[1]}<extra>%{fullData.name}</extra>",
            ), row=row_index, col=1)
        fig.update_yaxes(title_text=f"{label} ({unit})", row=row_index, col=1)
    style(fig, "Telemetry comparison / 25 m bins", "", "", max(370, 175 * len(channels)))
    fig.update_xaxes(title_text="Distance bin start (m)", row=len(channels), col=1)
    st.plotly_chart(fig, width="stretch")
