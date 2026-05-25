"""Option A — matplotlib sim-vs-real overlay (static PNG).

Reads one sim.csv produced by generate_simdata.py and renders a 6-panel
figure overlaying the model's integrated state against the rlog-measured
channels where both exist (speed, road-wheel steer). Predicted-only channels
(trajectory, yaw rate, lateral G) are shown alongside for context.

Output: out/sim_vs_real/<segment>/compare.png
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

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
    t = df["t_s"].to_numpy()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(3, 2, figsize=(14, 10))
    fig.suptitle(
        f"Sim vs Real — KS model on Tesla rlog inputs\n"
        f"segment 063c5f30 / cf682901 / 1   ({len(df)} rows @ 50 Hz, {t[-1]:.1f} s)",
        fontsize=12,
    )

    # 1. Trajectory (sim only — no measured GPS in this rlog)
    ax = axes[0, 0]
    ax.plot(df["x_m"], df["y_m"], color=SIM_COLOR, lw=1.4, label="sim")
    ax.scatter([df["x_m"].iat[0]], [df["y_m"].iat[0]], c="green", s=40, zorder=5, label="start")
    ax.scatter([df["x_m"].iat[-1]], [df["y_m"].iat[-1]], c="red", s=40, zorder=5, label="end")
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]")
    ax.set_title("Integrated trajectory (sim only)")
    ax.set_aspect("equal", adjustable="datalim"); ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=9)

    # 2. Speed: measured vs model state
    ax = axes[0, 1]
    ax.plot(t, df["v_mps"], color=REAL_COLOR, lw=1.2, label="real (v_mps)")
    ax.plot(t, df["v_state_mps"], color=SIM_COLOR, lw=1.2, ls="--", label="sim (v_state)")
    ax.set_xlabel("t [s]"); ax.set_ylabel("speed [m/s]")
    ax.set_title("Speed — real vs sim")
    ax.grid(True, alpha=0.3); ax.legend(loc="best", fontsize=9)

    # 3. Road-wheel steering: measured vs model state
    ax = axes[1, 0]
    ax.plot(t, df["delta_road_rad"], color=REAL_COLOR, lw=1.2, label="real (delta_road)")
    ax.plot(t, df["delta_state_rad"], color=SIM_COLOR, lw=1.2, ls="--", label="sim (delta_state)")
    ax.set_xlabel("t [s]"); ax.set_ylabel("steer [rad]")
    ax.set_title("Road-wheel steering — real vs sim")
    ax.grid(True, alpha=0.3); ax.legend(loc="best", fontsize=9)

    # 4. Longitudinal accel (driver input)
    ax = axes[1, 1]
    ax.plot(t, df["a_long_mps2"], color=REAL_COLOR, lw=1.0, label="real (a_long)")
    ax.set_xlabel("t [s]"); ax.set_ylabel("a_long [m/s²]")
    ax.set_title("Longitudinal acceleration (input)")
    ax.grid(True, alpha=0.3); ax.legend(loc="best", fontsize=9)

    # 5. Predicted yaw rate (no IMU truth in this rlog)
    ax = axes[2, 0]
    ax.plot(t, df["psi_dot_rads"], color=SIM_COLOR, lw=1.0)
    ax.set_xlabel("t [s]"); ax.set_ylabel("psi_dot [rad/s]")
    ax.set_title("Yaw rate — sim only (no IMU in rlog)")
    ax.grid(True, alpha=0.3)

    # 6. Predicted lateral G (no IMU truth)
    ax = axes[2, 1]
    ax.plot(t, df["a_y_mps2"], color=SIM_COLOR, lw=1.0)
    ax.set_xlabel("t [s]"); ax.set_ylabel("a_y [m/s²]")
    ax.set_title("Lateral acceleration — sim only (no IMU in rlog)")
    ax.grid(True, alpha=0.3)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out_path = OUT_DIR / "compare.png"
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
