"""Shared visual language for the dashboard and Plotly figures."""

import plotly.graph_objects as go
import streamlit as st

COLORS = ("#ef534d", "#55b9de", "#e7b866", "#9ac99c", "#ae99d2")
BG = "#11161c"
GRID = "#283039"

CSS = """
<style>
.stApp {background:#0b0e12;color:#e8ebee}
[data-testid="stSidebar"] {background:#101419;border-right:1px solid #252b32}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.6rem}
.block-container {padding:2rem 2.8rem 3rem;max-width:1700px}
h1,h2,h3 {letter-spacing:-.035em;color:#f1f3f5}
h1 {font-size:2rem!important;font-weight:650!important;margin-bottom:.1rem!important}
h2,h3 {font-weight:600!important}
p, label {color:#c3cbd3}
[data-testid="stCaptionContainer"] p {color:#97a3ae;font-size:.78rem}
[data-testid="stMetric"] {background:#151a20;border:1px solid #29313a;
 border-radius:2px;padding:1rem 1.15rem;min-height:110px}
[data-testid="stMetricLabel"] p {color:#9ba6b0;font-size:.72rem;letter-spacing:.08em}
[data-testid="stMetricValue"] {font-size:1.75rem;color:#f1f4f6}
[data-testid="stSidebar"] [role="radiogroup"] {gap:3px}
[data-testid="stSidebar"] [role="radiogroup"] label {background:transparent;
 border-left:2px solid transparent;padding:.5rem .65rem;color:#b5bec8}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
 background:#20262d;border-left:2px solid #ef534d;color:#fff}
[data-testid="stSidebar"] [role="radiogroup"] label > div > div:first-child {display:none}
[data-baseweb="select"] > div {background:#171d24!important;border:1px solid #333c46!important;
 border-radius:2px!important;color:#e9edf0!important}
[data-baseweb="popover"] {color:#e9edf0}
[data-testid="stExpander"] {border:1px solid #29313a;border-radius:2px}
hr {border-color:#29313a}
.apex-brand {font-size:1.62rem;font-weight:750;letter-spacing:-.06em;color:#f4f5f6}
.apex-brand span {color:#ed554e}
.apex-eyebrow {color:#87939e;font-size:.67rem;font-weight:650;letter-spacing:.14em;text-transform:uppercase}
.apex-section {font-size:.72rem;font-weight:700;letter-spacing:.11em;text-transform:uppercase;
 color:#b6c1ca;border-bottom:1px solid #2b333d;padding-bottom:.6rem;margin:1.1rem 0 .4rem}
.apex-header {border-bottom:1px solid #303740;padding-bottom:.8rem;margin-bottom:.6rem}
.apex-status {color:#afc8b7;font-size:.74rem;letter-spacing:.08em}
.apex-kpis {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:1.2rem 0}
@media (max-width: 1200px) {.apex-kpis {grid-template-columns:repeat(2,minmax(0,1fr))}}
.apex-kpi {background:#151a20;border:1px solid #29313a;padding:14px 16px;min-height:94px}
.apex-kpi-label {color:#a7b2bc;font-size:.68rem;letter-spacing:.09em;text-transform:uppercase}
.apex-kpi-value {color:#f3f5f6;font-size:1.5rem;font-weight:650;line-height:1.25;margin-top:8px}
.apex-kpi-note {color:#9ba6b0;font-size:.72rem;margin-top:3px}
</style>
"""


def section(title):
    st.markdown(f'<div class="apex-section">{title}</div>', unsafe_allow_html=True)


def style(fig: go.Figure, title="", x="", y="", height=320):
    fig.update_layout(
        title={"text": title, "font": {"size": 14, "color": "#e6eaed"}},
        paper_bgcolor=BG, plot_bgcolor=BG, font={"family": "Arial, sans-serif", "size": 12, "color": "#bbc5ce"},
        height=height, margin={"l": 48, "r": 18, "t": 48, "b": 45},
        legend={"orientation": "h", "y": 1.04, "x": 1, "xanchor": "right", "font": {"size": 11}},
        hoverlabel={"bgcolor": "#202832", "font_color": "#f0f3f5", "bordercolor": "#46515c"},
        xaxis_title=x, yaxis_title=y,
    )
    fig.update_xaxes(showgrid=True, gridcolor=GRID, zeroline=False, linecolor=GRID, ticks="outside")
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False, linecolor=GRID, ticks="outside")
    return fig
