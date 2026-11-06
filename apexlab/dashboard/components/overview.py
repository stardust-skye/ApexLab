import streamlit as st
import plotly.graph_objects as go
from html import escape

from apexlab.analytics import analyze_laps, race_overview
from apexlab.dashboard.helpers import driver_options
from apexlab.dashboard.helpers import format_value
from apexlab.dashboard.theme import COLORS, section, style


def render(data, metadata, report, control=None):
    info = metadata.get("data", {}).get("session_info", {})
    meeting = info.get("Meeting", {})
    st.subheader(meeting.get("OfficialName", meeting.get("Name", "Race overview")))
    st.caption(f"{info.get('Name', 'Race')}  ·  {meeting.get('Location', 'Location unavailable')}  ·  "
               f"Local start: {info.get('StartDate', 'unavailable')}  ·  UTC offset: {info.get('GmtOffset', 'unavailable')}")
    overview = race_overview(data)
    fastest = overview["fastest_lap"]
    cards = [
        ("Drivers", f"{overview['drivers']:,}", "Session entries"),
        ("Recorded laps", f"{overview['recorded_laps']:,}", "Timing records"),
        ("Telemetry samples", f"{overview['telemetry_samples']:,}", "Available observations"),
        ("Fastest lap", format_value(fastest["time"], " s", 3) if fastest else "Unavailable",
         f"{fastest['drv']} · L{fastest['lap']}" if fastest else "No valid lap time"),
    ]
    html = "".join(f'<div class="apex-kpi"><div class="apex-kpi-label">{escape(label)}</div>'
                   f'<div class="apex-kpi-value">{escape(value)}</div>'
                   f'<div class="apex-kpi-note">{escape(note)}</div></div>' for label, value, note in cards)
    st.markdown(f'<div class="apex-kpis">{html}</div>', unsafe_allow_html=True)
    left, right = st.columns([1.7, 1], gap="medium")
    with left:
        section("Race pace / lap progression")
        options = [d for d in driver_options(data) if (data.laps["drv"] == d).any()]
        if options:
            selected = st.multiselect("Drivers shown", options, default=options[:2], key="overview_drivers")
            fig = go.Figure()
            for index, driver in enumerate(selected):
                laps = analyze_laps(data, driver)["laps"].sort_values("lap")
                fig.add_trace(go.Scatter(x=laps["lap"], y=laps["time"].where(laps["time"] > 0),
                    mode="markers", marker={"size": 6, "color": COLORS[index % len(COLORS)]}, name=driver,
                    hovertemplate="Lap %{x}<br>%{y:.3f} s<extra>%{fullData.name}</extra>"))
            st.plotly_chart(style(fig, "Recorded lap times", "Lap", "Lap time (s)", 320), width="stretch")
        else:
            st.info("No lap timing available.")
        section("Driver performance / selected")
        if options and selected:
            rows = []
            for driver in selected:
                stats = analyze_laps(data, driver)
                rows.append({"Driver": driver, "Timed laps": stats["timed_laps"],
                             "Mean (s)": stats["mean_seconds"], "Median (s)": stats["median_seconds"],
                             "Consistency SD (s)": stats["std_seconds"]})
            st.dataframe(rows, hide_index=True, width="stretch")
            st.caption("All positive recorded laps; sample SD. Pit and safety-car laps included.")
    with right:
        section("Session integrity / coverage")
        for key, label in (("laps_without_telemetry", "Recorded laps without telemetry"),
                           ("telemetry_without_laps", "Telemetry without lap timing"),
                           ("unknown_lap_drivers", "Unknown lap drivers"),
                           ("unknown_telemetry_drivers", "Unknown telemetry drivers")):
            values = data.coverage[key]
            if values:
                st.warning(f"{label}: {values}")
            else:
                st.caption(f"{label}: none")
        failures = report.get("validation_failures", [])
        if failures:
            with st.expander(f"Quality checks / {len(failures)} findings", expanded=True):
                st.dataframe([{"Check": item["rule"], "Count": item["count"]} for item in failures],
                             hide_index=True, width="stretch")
        else:
            st.caption("No validation failures recorded.")
        section("Race control / event timeline")
        if control is None:
            st.info("Race-control data unavailable.")
        elif control.empty:
            st.info("No race-control events recorded.")
        else:
            events = control.sort_values("time", ascending=False)
            st.caption(f"{len(events)} messages · latest first · UTC source timestamps")
            for _, row in events.head(6).iterrows():
                st.markdown(f"**{row['time']}**  ·  {row['cat']}\n\n{row['msg']}")
            with st.expander("All race-control messages"):
                st.dataframe(events, hide_index=True, width="stretch")
