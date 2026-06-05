"""Sanity-check plot: read each sim.csv produced by
webinar-meta/skills/build-simdata/build_simdata.py and render a small
multi-panel figure per segment under simdata/<...>/sim.png.

Same layout as run_ks_synthetic.py's plot, plus a per-segment trajectory.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

KB003 = Path(__file__).resolve().parents[1]
SIMDATA = KB003 / "data" / "sim" / "segments" / "TESLA_MODEL_3"


def plot_one(csv_path: Path) -> Path:
    df = pd.read_csv(csv_path)
    out = csv_path.with_suffix(".png")

    fig, axes = plt.subplots(3, 2, figsize=(13, 10))
    seg_label = "/".join(csv_path.parts[-4:-1])
    fig.suptitle(
        f"KS on real Tesla rlog inputs — {seg_label}\n"
        f"openpilot-canonical params; CSV: {csv_path.name}",
        fontsize=11,
    )

    # 1. Trajectory
    ax = axes[0, 0]
    ax.plot(df["x_m"], df["y_m"], lw=1.4)
    ax.scatter([df["x_m"].iat[0]], [df["y_m"].iat[0]], c="green", s=40, zorder=5, label="start")
    ax.scatter([df["x_m"].iat[-1]], [df["y_m"].iat[-1]], c="red", s=40, zorder=5, label="end")
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]")
    ax.set_title("Integrated trajectory")
    ax.set_aspect("equal", adjustable="datalim"); ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=9)

    # 2. Steering (input)
    ax = axes[0, 1]
    ax.plot(df["t_s"], df["delta_wheel_deg"], lw=1.2, label="wheel")
    ax2 = ax.twinx()
    ax2.plot(df["t_s"], np.degrees(df["delta_road_rad"]), lw=1.0, color="C1", alpha=0.7, label="road wheel")
    ax.set_xlabel("t [s]"); ax.set_ylabel("delta wheel [deg]")
    ax2.set_ylabel("delta road [deg]", color="C1")
    ax.set_title("Steering (input) — measured from CAN")
    ax.grid(True, alpha=0.3); ax.axhline(0, color="black", lw=0.5)

    # 3. Longitudinal: a, accel pedal
    ax = axes[1, 0]
    ax.plot(df["t_s"], df["a_long_mps2"], lw=1.2, label="a_long (derived)")
    ax2 = ax.twinx()
    ax2.plot(df["t_s"], df["accel_pedal_pct"], lw=1.0, color="C2", alpha=0.5, label="accel %")
    ax.set_xlabel("t [s]"); ax.set_ylabel("a_long [m/s²]")
    ax2.set_ylabel("accel pedal [%]", color="C2")
    ax.set_title("Longitudinal: derived a vs accel pedal")
    ax.grid(True, alpha=0.3); ax.axhline(0, color="black", lw=0.5)

    # 4. Speed + drive torque
    ax = axes[1, 1]
    ax.plot(df["t_s"], df["v_mps"], lw=1.2, label="v")
    ax2 = ax.twinx()
    ax2.plot(df["t_s"], df["di_torque_actual_nm"], lw=1.0, color="C3", alpha=0.5)
    ax.set_xlabel("t [s]"); ax.set_ylabel("v [m/s]")
    ax2.set_ylabel("DI_torqueActual [Nm]", color="C3")
    ax.set_title("Speed + drive-inverter torque (regen visible as negative)")
    ax.grid(True, alpha=0.3)

    # 5. KS yaw rate
    ax = axes[2, 0]
    ax.plot(df["t_s"], np.degrees(df["psi_dot_rads"]), lw=1.2)
    ax.set_xlabel("t [s]"); ax.set_ylabel("psi_dot [deg/s]")
    ax.set_title("KS-predicted yaw rate\n(no Tesla-IMU comparison available in this rlog)")
    ax.grid(True, alpha=0.3); ax.axhline(0, color="black", lw=0.5)

    # 6. KS lateral G
    ax = axes[2, 1]
    ax.plot(df["t_s"], df["a_y_mps2"], lw=1.2)
    ax.axhspan(-5.0, 5.0, color="green", alpha=0.06, label="ST linear-honest (±5 m/s²)")
    ax.set_xlabel("t [s]"); ax.set_ylabel("a_y [m/s²]")
    ax.set_title("KS-predicted lateral G")
    ax.grid(True, alpha=0.3); ax.axhline(0, color="black", lw=0.5)
    ax.legend(loc="best", fontsize=9)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def main():
    csvs = sorted(SIMDATA.rglob("sim.csv"))
    for csv in csvs:
        png = plot_one(csv)
        print(f"  → {png.relative_to(KB003)}")


if __name__ == "__main__":
    main()
