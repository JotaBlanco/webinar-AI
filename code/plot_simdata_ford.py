"""Sanity-check plot for Ford simdata.

Unlike the Tesla equivalent, the Ford rlog gives us measured yaw rate and
lateral acceleration straight from CAN — so this plot shows KS *prediction
versus measurement* side by side, plus the residual. That is the entire point
of the workshop's "compare" beat (step 4 of the workshop outline).

One PNG per sim.csv at data/sim/segments/<platform>/<...>/sim.png.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

KB003 = Path(__file__).resolve().parents[1]
SIM_BASE = KB003 / "data" / "sim" / "segments"
FORD_PLATFORMS = ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1")


def plot_one(csv_path: Path) -> Path:
    df = pd.read_csv(csv_path)
    out = csv_path.with_suffix(".png")

    fig, axes = plt.subplots(3, 2, figsize=(13, 11))
    platform = csv_path.parts[-5]  # .../<platform>/<device>/<route>/<idx>/sim.csv
    seg_label = "/".join(csv_path.parts[-4:-1])
    fig.suptitle(
        f"KS on real {platform} rlog inputs — {seg_label}\n"
        f"openpilot-canonical params; CSV: {csv_path.name}",
        fontsize=11,
    )

    t = df["t_s"]

    # 1. Trajectory
    ax = axes[0, 0]
    ax.plot(df["x_m"], df["y_m"], lw=1.4)
    ax.scatter([df["x_m"].iat[0]], [df["y_m"].iat[0]], c="green", s=40, zorder=5, label="start")
    ax.scatter([df["x_m"].iat[-1]], [df["y_m"].iat[-1]], c="red",   s=40, zorder=5, label="end")
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]")
    ax.set_title("KS-integrated trajectory (open-loop)")
    ax.set_aspect("equal", adjustable="datalim"); ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=9)

    # 2. Speed + steering
    ax = axes[0, 1]
    ax.plot(t, df["v_mps"], lw=1.2, color="C0", label="v [m/s]")
    ax.set_ylabel("v [m/s]", color="C0"); ax.tick_params(axis="y", labelcolor="C0")
    ax2 = ax.twinx()
    ax2.plot(t, df["delta_wheel_deg"], lw=1.0, color="C1", alpha=0.7,
             label="steering wheel [°]")
    ax2.set_ylabel("δ_wheel [°]", color="C1"); ax2.tick_params(axis="y", labelcolor="C1")
    ax.set_xlabel("t [s]")
    ax.set_title("Inputs from CAN: speed and steering")
    ax.grid(True, alpha=0.3); ax.axhline(0, color="black", lw=0.5)

    # 3. Longitudinal: measured a_long
    ax = axes[1, 0]
    ax.plot(t, df["a_long_mps2"], lw=1.2, color="C0", label="a_long (measured, BrakeSnData_3)")
    ax2 = ax.twinx()
    ax2.plot(t, df["accel_pedal_pct"], lw=1.0, color="C2", alpha=0.5, label="accel pedal [%]")
    ax2.plot(t, 100 * df["brake_pressed"], lw=1.0, color="C3", alpha=0.5, label="brake pressed")
    ax.set_xlabel("t [s]"); ax.set_ylabel("a_long [m/s²]")
    ax2.set_ylabel("pedal [%] / brake flag", color="gray")
    ax.set_title("Longitudinal: measured a_long vs driver pedals")
    ax.grid(True, alpha=0.3); ax.axhline(0, color="black", lw=0.5)
    ax.legend(loc="upper left", fontsize=8)
    ax2.legend(loc="upper right", fontsize=8)

    # 4. KS-PREDICTED vs MEASURED yaw rate — the headline panel
    ax = axes[1, 1]
    psi_dot_meas = np.degrees(df["yaw_rate_meas_rads"])
    psi_dot_pred = np.degrees(df["yaw_rate_pred_rads"])
    ax.plot(t, psi_dot_meas, lw=1.5, color="black",   label="measured (Yaw_Data_FD1)")
    ax.plot(t, psi_dot_pred, lw=1.2, color="C0", alpha=0.85, label="KS predicted (v/L · tan δ)")
    rms = np.sqrt(np.mean((psi_dot_meas - psi_dot_pred) ** 2))
    ax.set_xlabel("t [s]"); ax.set_ylabel("ψ̇ [deg/s]")
    ax.set_title(f"Yaw rate — pred vs meas   (RMS residual = {rms:.2f} °/s)")
    ax.grid(True, alpha=0.3); ax.axhline(0, color="black", lw=0.5)
    ax.legend(loc="best", fontsize=9)

    # 5. KS-PREDICTED vs MEASURED lateral acceleration
    ax = axes[2, 0]
    ax.plot(t, df["a_lat_meas_mps2"], lw=1.5, color="black", label="measured (BrakeSnData_3)")
    ax.plot(t, df["a_y_pred_mps2"],   lw=1.2, color="C0", alpha=0.85, label="KS predicted (v · ψ̇)")
    rms_ay = np.sqrt(np.mean((df["a_lat_meas_mps2"] - df["a_y_pred_mps2"]) ** 2))
    ax.axhspan(-5.0, 5.0, color="green", alpha=0.05, label="ST linear-honest (±5 m/s²)")
    ax.set_xlabel("t [s]"); ax.set_ylabel("a_y [m/s²]")
    ax.set_title(f"Lateral G — pred vs meas   (RMS residual = {rms_ay:.2f} m/s²)")
    ax.grid(True, alpha=0.3); ax.axhline(0, color="black", lw=0.5)
    ax.legend(loc="best", fontsize=8)

    # 6. Residuals over time
    ax = axes[2, 1]
    ax.plot(t, np.degrees(df["yaw_rate_resid_rads"]), lw=1.0, color="C3",
            label="ψ̇ residual [°/s]")
    ax.set_ylabel("ψ̇ residual [°/s]", color="C3"); ax.tick_params(axis="y", labelcolor="C3")
    ax2 = ax.twinx()
    ax2.plot(t, df["a_y_resid_mps2"], lw=1.0, color="C4", label="a_y residual [m/s²]")
    ax2.set_ylabel("a_y residual [m/s²]", color="C4"); ax2.tick_params(axis="y", labelcolor="C4")
    ax.set_xlabel("t [s]")
    ax.set_title("Residuals (measured − KS-predicted)")
    ax.grid(True, alpha=0.3); ax.axhline(0, color="black", lw=0.5)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(FORD_PLATFORMS)
    for plat in targets:
        root = SIM_BASE / plat
        if not root.is_dir():
            print(f"  no simdata for {plat}; skipping")
            continue
        csvs = sorted(root.rglob("sim.csv"))
        for csv in csvs:
            png = plot_one(csv)
            print(f"  → {png.relative_to(KB003)}")


if __name__ == "__main__":
    main()
