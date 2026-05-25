"""Option B — Plotly interactive HTML sim-vs-real overlay.

Same panels as the matplotlib version, but as a self-contained HTML file with
synchronised x-axis cursors across all time-series subplots (hover on one
panel highlights the same instant in the others).

Output: out/sim_vs_real/<segment>/compare.html
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

KB003 = Path(__file__).resolve().parents[1]
SEGMENT_CSV = (
    KB003
    / "data/sim/segments/TESLA_MODEL_3/063c5f30b8e68fae/00000000--cf682901f4/1/sim.csv"
)
OUT_DIR = Path(__file__).parent / "out/sim_vs_real/063c5f30__cf682901__1"

REAL_COLOR = "#d62728"
SIM_COLOR = "#1f77b4"


def main() -> None:
    df = pd.read_csv(SEGMENT_CSV)
    t = df["t_s"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    fig = make_subplots(
        rows=3,
        cols=2,
        subplot_titles=(
            "Trajectory (sim only)",
            "Speed — real vs sim",
            "Road-wheel steering — real vs sim",
            "Longitudinal acceleration (input)",
            "Yaw rate — sim only",
            "Lateral acceleration — sim only",
        ),
        specs=[
            [{"type": "xy"}, {"type": "xy"}],
            [{"type": "xy"}, {"type": "xy"}],
            [{"type": "xy"}, {"type": "xy"}],
        ],
        horizontal_spacing=0.08,
        vertical_spacing=0.10,
    )

    # 1. Trajectory
    fig.add_trace(
        go.Scatter(x=df["x_m"], y=df["y_m"], mode="lines",
                   line=dict(color=SIM_COLOR, width=1.6),
                   name="sim path", hovertemplate="x=%{x:.1f} m<br>y=%{y:.1f} m"),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=[df["x_m"].iat[0]], y=[df["y_m"].iat[0]], mode="markers",
                   marker=dict(color="green", size=10), name="start", showlegend=False),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=[df["x_m"].iat[-1]], y=[df["y_m"].iat[-1]], mode="markers",
                   marker=dict(color="red", size=10), name="end", showlegend=False),
        row=1, col=1,
    )

    # 2. Speed
    fig.add_trace(go.Scatter(x=t, y=df["v_mps"], name="real (v_mps)",
                             line=dict(color=REAL_COLOR, width=1.4)),
                  row=1, col=2)
    fig.add_trace(go.Scatter(x=t, y=df["v_state_mps"], name="sim (v_state)",
                             line=dict(color=SIM_COLOR, width=1.4, dash="dash")),
                  row=1, col=2)

    # 3. Steering
    fig.add_trace(go.Scatter(x=t, y=df["delta_road_rad"], name="real (delta_road)",
                             line=dict(color=REAL_COLOR, width=1.4)),
                  row=2, col=1)
    fig.add_trace(go.Scatter(x=t, y=df["delta_state_rad"], name="sim (delta_state)",
                             line=dict(color=SIM_COLOR, width=1.4, dash="dash")),
                  row=2, col=1)

    # 4. Longitudinal accel
    fig.add_trace(go.Scatter(x=t, y=df["a_long_mps2"], name="real (a_long)",
                             line=dict(color=REAL_COLOR, width=1.2)),
                  row=2, col=2)

    # 5. Yaw rate (sim)
    fig.add_trace(go.Scatter(x=t, y=df["psi_dot_rads"], name="sim (psi_dot)",
                             line=dict(color=SIM_COLOR, width=1.2)),
                  row=3, col=1)

    # 6. Lateral G (sim)
    fig.add_trace(go.Scatter(x=t, y=df["a_y_mps2"], name="sim (a_y)",
                             line=dict(color=SIM_COLOR, width=1.2)),
                  row=3, col=2)

    # Sync time-series x-axes (panels 2-6) on hover
    for (r, c) in [(1, 2), (2, 1), (2, 2), (3, 1), (3, 2)]:
        fig.update_xaxes(matches="x2", row=r, col=c, title_text="t [s]")
    fig.update_yaxes(title_text="speed [m/s]", row=1, col=2)
    fig.update_yaxes(title_text="steer [rad]", row=2, col=1)
    fig.update_yaxes(title_text="a_long [m/s²]", row=2, col=2)
    fig.update_yaxes(title_text="psi_dot [rad/s]", row=3, col=1)
    fig.update_yaxes(title_text="a_y [m/s²]", row=3, col=2)
    fig.update_xaxes(title_text="x [m]", row=1, col=1)
    fig.update_yaxes(title_text="y [m]", row=1, col=1, scaleanchor="x", scaleratio=1)

    fig.update_layout(
        title=dict(
            text="Sim vs Real — KS model on Tesla rlog inputs<br>"
                 "<sub>segment 063c5f30 / cf682901 / 1 — "
                 f"{len(df)} rows @ 50 Hz, {t.iat[-1]:.1f} s</sub>",
            x=0.5,
        ),
        height=900,
        hovermode="x unified",
        legend=dict(orientation="h", y=-0.07),
    )

    out_path = OUT_DIR / "compare.html"
    fig.write_html(str(out_path), include_plotlyjs="cdn")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
