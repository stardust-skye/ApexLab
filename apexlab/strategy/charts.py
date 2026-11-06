"""Reusable figures for observational stint research."""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from apexlab.dashboard.theme import COLORS, style


def lap_progression(laps):
    fig = go.Figure()
    for index, (segment, group) in enumerate(laps.groupby("segment_id", sort=False)):
        fig.add_trace(go.Scatter(x=group["lap"], y=group["time"], mode="markers",
                                 name=f"Stint {group['source_stint'].iloc[0]}",
                                 marker_color=COLORS[index % len(COLORS)],
                                 customdata=group[["source_file", "source_row"]],
                                 hovertemplate="Lap %{x}<br>%{y:.3f} s<br>%{customdata[0]} row %{customdata[1]}<extra>%{fullData.name}</extra>"))
    return style(fig, "Lap time / source-reported stints", "Race lap", "Lap time (s)")


def life_trend(laps, fit=None):
    fig = go.Figure()
    for eligible, group in laps.groupby("eligible"):
        fig.add_trace(go.Scatter(x=group["reported_tire_life"], y=group["time"], mode="markers",
                                 name="Model sample" if eligible else "Excluded / incomplete",
                                 marker={"color": COLORS[0] if eligible else "#84919b", "size": 7},
                                 customdata=group[["lap", "source_file", "source_row"]],
                                 hovertemplate="Reported life %{x}<br>%{y:.3f} s<br>Lap %{customdata[0]}<br>%{customdata[1]} row %{customdata[2]}<extra>%{fullData.name}</extra>"))
    if fit is not None:
        x = np.sort(fit["observations"]["reported_tire_life"].unique())
        y = fit["intercept_seconds"] + fit["slope_seconds_per_lap"] * x
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name="OLS fitted trend", line={"color": COLORS[1]}))
    return style(fig, "Lap time / reported tire life", "Reported tire life (laps)", "Lap time (s)")


def residual_uncertainty(fit):
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Residual by reported life", "Slope bootstrap interval"))
    frame = fit["observations"]
    fig.add_trace(go.Scatter(x=frame["reported_tire_life"], y=frame["residual_seconds"],
                             mode="markers", marker_color=COLORS[0], name="Residual"), row=1, col=1)
    low, high = fit["slope_interval_95"]
    fig.add_trace(go.Scatter(x=[fit["slope_seconds_per_lap"]], y=["OLS slope"], mode="markers",
                             error_x={"type": "data", "symmetric": False,
                                      "array": [max(0, high - fit["slope_seconds_per_lap"])],
                                      "arrayminus": [max(0, fit["slope_seconds_per_lap"] - low)]},
                             marker_color=COLORS[1], name="95% bootstrap"), row=1, col=2)
    fig.update_xaxes(title_text="Reported tire life (laps)", row=1, col=1)
    fig.update_yaxes(title_text="Residual (s)", row=1, col=1)
    fig.update_xaxes(title_text="Slope (s / reported life lap)", row=1, col=2)
    return style(fig, "Residuals and descriptive uncertainty", height=330)
