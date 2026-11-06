"""ApexLab Streamlit entry point."""

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from apexlab.analytics import load_race
from apexlab.analytics.data import DEFAULT_PATH
from apexlab.dashboard.components import comparison, corner_analysis, lap_analysis, overview, telemetry, tire_analysis
from apexlab.dashboard.theme import CSS


@st.cache_resource(show_spinner="Loading race telemetry...")
def load_data(directory, fingerprint):
    del fingerprint
    path = Path(directory)
    race = load_race(path)
    with (path / "session_metadata.json").open(encoding="utf-8") as file:
        metadata = json.load(file)
    with (path / "data_quality_report.json").open(encoding="utf-8") as file:
        report = json.load(file)
    return race, metadata, report


@st.cache_data(show_spinner=False)
def load_race_control(directory, fingerprint):
    del fingerprint
    path = Path(directory) / "race_control.csv"
    if not path.exists():
        return None
    return pd.read_csv(path, keep_default_na=False, na_values=["\\N"], dtype={"dNum": "string"})


def main():
    st.set_page_config(page_title="ApexLab | Race Engineering", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.sidebar.markdown("<div class='apex-brand'>APEX<span>LAB</span></div>"
                        "<div class='apex-eyebrow'>Race engineering intelligence</div>", unsafe_allow_html=True)
    st.sidebar.markdown("---")
    page = st.sidebar.radio("WORKSPACE", ["Race Overview", "Driver Comparison", "Telemetry Explorer",
                                          "Lap Analysis", "Corner Analysis", "Tire & Stint Analysis"])
    directory = Path(os.environ.get("APEXLAB_DATA_DIR", str(DEFAULT_PATH))).resolve()
    files = ("drivers.csv", "laps.csv", "telemetry.csv", "circuit_corners.csv",
             "session_metadata.json", "data_quality_report.json")
    try:
        fingerprint = tuple((name, (directory / name).stat().st_mtime_ns, (directory / name).stat().st_size)
                            for name in files)
        data, metadata, report = load_data(str(directory), fingerprint)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        st.error(f"Cannot load processed race data from {directory}: {exc}")
        st.info("Run `python -m apexlab.ingestion` after acquiring raw race data.")
        st.stop()
    info = metadata.get("data", {}).get("session_info", {})
    meeting = info.get("Meeting", {})
    event = meeting.get("Name", "Race session")
    session = info.get("Name", "Race")
    st.sidebar.markdown("---")
    st.sidebar.markdown("<div class='apex-eyebrow'>Active dataset</div>", unsafe_allow_html=True)
    st.sidebar.selectbox("Grand Prix", [event], key="event_selector")
    st.sidebar.selectbox("Session", [session], key="session_selector")
    gaps = (len(data.coverage["laps_without_telemetry"]) + len(data.coverage["telemetry_without_laps"])
            + len(data.coverage["unknown_lap_drivers"]) + len(data.coverage["unknown_telemetry_drivers"]))
    st.sidebar.caption(f"LOCAL PROCESSED DATA  ·  {len(data.drivers)} DRIVERS\n\n"
                       f"{'COVERAGE ISSUES: ' + str(gaps) if gaps else 'NO COVERAGE GAPS'}")
    refreshed = datetime.fromtimestamp((directory / "data_quality_report.json").stat().st_mtime).astimezone()
    st.markdown(f"<div class='apex-eyebrow'>Session workspace / {page}</div>", unsafe_allow_html=True)
    st.title(page)
    status = "PARTIAL" if gaps else "QUALITY FLAGS" if report.get("validation_failures") else "AVAILABLE"
    st.caption(f"{event}  /  {session}     ·     DATASET {status}"
               f"     ·     Quality report updated {refreshed:%d %b %Y, %H:%M %Z}")
    st.markdown("<div class='apex-header'></div>", unsafe_allow_html=True)
    if page == "Race Overview":
        control_path = directory / "race_control.csv"
        control_fingerprint = (control_path.stat().st_mtime_ns, control_path.stat().st_size) if control_path.exists() else None
        try:
            control = load_race_control(str(directory), control_fingerprint)
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            st.error(f"Cannot load race control events: {exc}")
            control = None
        overview.render(data, metadata, report, control)
    elif page == "Driver Comparison":
        comparison.render(data)
    elif page == "Telemetry Explorer":
        telemetry.render(data)
    elif page == "Lap Analysis":
        lap_analysis.render(data)
    elif page == "Corner Analysis":
        corner_analysis.render(data)
    else:
        tire_analysis.render(data)


if __name__ == "__main__":
    main()
