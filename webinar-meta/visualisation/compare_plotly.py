"""Plotly N-agent interactive HTML overlay.

Renders one segment with measured truth + V0 baseline + each agent in a
shared 6-panel layout (trajectory, yaw rate, residual, steering, speed,
yaw rate residual).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from _runner import RunResult, Schema, Segment

OUT_ROOT = Path(__file__).resolve().parent / "out"


def render(seg: Segment, df, schema: Schema, runs: list[RunResult],
           out_path: Path | None = None) -> Path:
    """Write a single HTML file overlaying every run on the segment."""
    t = df["t_s"]

    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=(
            "Trajectory (x,y)",
            "Yaw rate (rad/s)",
            "Yaw-rate residual (run – measured)",
            "Steering — δ_road (rad)",
            "Speed (m/s)",
            "Trajectory error vs measured (m)",
        ),
        horizontal_spacing=0.08, vertical_spacing=0.10,
        specs=[
            [{"type": "xy"}, {"type": "xy"}],
            [{"type": "xy"}, {"type": "xy"}],
            [{"type": "xy"}, {"type": "xy"}],
        ],
    )

    truth = next((r for r in runs if r.is_truth), None)
    measured_yaw = truth.yaw_rate if truth is not None else None

    for r in runs:
        # Trajectory panel
        fig.add_trace(go.Scatter(
            x=r.x, y=r.y, mode="lines", name=r.name,
            line=dict(color=r.color_hex, width=(2.2 if r.is_truth else 1.6),
                      dash=("solid" if not r.is_baseline else "dot")),
            legendgroup=r.name, hovertemplate=f"<b>{r.name}</b><br>x=%{{x:.1f}} m<br>y=%{{y:.1f}} m",
        ), row=1, col=1)

        # Yaw-rate panel
        fig.add_trace(go.Scatter(
            x=t, y=r.yaw_rate, name=r.name, showlegend=False,
            line=dict(color=r.color_hex, width=(2.0 if r.is_truth else 1.4),
                      dash=("solid" if not r.is_baseline else "dot")),
            legendgroup=r.name,
        ), row=1, col=2)

        # Yaw-rate residual
        if not r.is_truth and measured_yaw is not None:
            fig.add_trace(go.Scatter(
                x=t, y=r.yaw_rate - measured_yaw, name=r.name, showlegend=False,
                line=dict(color=r.color_hex, width=1.2), legendgroup=r.name,
            ), row=2, col=1)

        # XY error vs measured truth (Euclidean distance) — bottom-right
        if not r.is_truth and truth is not None:
            err = np.hypot(r.x - truth.x, r.y - truth.y)
            fig.add_trace(go.Scatter(
                x=t, y=err, name=r.name, showlegend=False,
                line=dict(color=r.color_hex, width=1.2), legendgroup=r.name,
            ), row=3, col=2)

    # Driver-input panels (one trace each, sourced from sim.csv)
    fig.add_trace(go.Scatter(
        x=t, y=df["delta_road_rad"], name="δ_road (input)", showlegend=False,
        line=dict(color="#888888", width=1.2),
    ), row=2, col=2)
    fig.add_trace(go.Scatter(
        x=t, y=df["v_mps"], name="v (input)", showlegend=False,
        line=dict(color="#888888", width=1.2),
    ), row=3, col=1)

    # Start/end markers
    if truth is not None:
        fig.add_trace(go.Scatter(
            x=[truth.x[0]], y=[truth.y[0]], mode="markers",
            marker=dict(color="green", size=10, symbol="circle"),
            name="start", showlegend=False,
        ), row=1, col=1)

    fig.update_xaxes(title_text="x [m]", row=1, col=1)
    fig.update_yaxes(title_text="y [m]", row=1, col=1, scaleanchor="x", scaleratio=1)
    fig.update_xaxes(title_text="t [s]", row=1, col=2)
    fig.update_yaxes(title_text="ψ̇ [rad/s]", row=1, col=2)
    fig.update_xaxes(title_text="t [s]", row=2, col=1)
    fig.update_yaxes(title_text="Δψ̇ [rad/s]", row=2, col=1)
    fig.update_xaxes(title_text="t [s]", row=2, col=2)
    fig.update_yaxes(title_text="δ_road [rad]", row=2, col=2)
    fig.update_xaxes(title_text="t [s]", row=3, col=1)
    fig.update_yaxes(title_text="v [m/s]", row=3, col=1)
    fig.update_xaxes(title_text="t [s]", row=3, col=2)
    fig.update_yaxes(title_text="‖xy − xy_meas‖ [m]", row=3, col=2)

    fig.update_layout(
        title=dict(
            text=f"<b>{seg.platform}</b> — {seg.device[:8]} / {seg.route[:14]} / #{seg.idx}"
                 f"<br><sub>{len(df)} samples @ 50 Hz, {float(t.iat[-1]):.1f} s</sub>",
            x=0.5,
        ),
        height=1000, hovermode="x unified",
        legend=dict(orientation="h", y=-0.06, x=0.5, xanchor="center"),
        margin=dict(t=90, l=60, r=30, b=60),
    )

    if out_path is None:
        out_dir = OUT_ROOT / seg.slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "compare.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out_path), include_plotlyjs="cdn")
    return out_path
