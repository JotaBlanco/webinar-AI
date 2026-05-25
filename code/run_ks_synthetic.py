"""Workshop minute-one demo: KS model on a synthetic Tesla Model 3 drive.

Run:
    python run_ks_synthetic.py

Outputs `out/ks_synthetic.png` — a six-panel figure:

    1. Bird's-eye trajectory (x vs y)
    2. Steering angle delta(t)
    3. Longitudinal acceleration a(t)
    4. Speed v(t)
    5. Predicted yaw rate psi_dot(t)
    6. Predicted lateral acceleration a_y(t)

This script has no rlog dependency. It exists to prove the spine runs today
and to give the workshop a 60-second visual the audience can react to before
real data is plugged in.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from ks_model import KSState, simulate_ks
from parameters import TESLA_MODEL_3
from synthetic_inputs import make_demo_inputs


OUT_DIR = Path(__file__).resolve().parent / "out"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)

    inp = make_demo_inputs(duration_s=60.0, sample_rate_hz=100.0)
    initial = KSState(x=0.0, y=0.0, psi=0.0, v=25.0, delta=0.0)
    traj = simulate_ks(inp, initial, TESLA_MODEL_3, clamp_delta_to_measured=True)

    # ---- Plot ----------------------------------------------------------------
    fig, axes = plt.subplots(3, 2, figsize=(13, 10))
    fig.suptitle(
        "KS — Kinematic Single-Track on synthetic Tesla Model 3 drive\n"
        f"L = {TESLA_MODEL_3.L:.3f} m  (parameters from vehicle-tesla-model-3.md)",
        fontsize=12,
    )

    # Panel 1 — trajectory (top-down)
    ax = axes[0, 0]
    ax.plot(traj.x, traj.y, lw=1.6)
    ax.scatter([traj.x[0]], [traj.y[0]], c="green", s=40, zorder=5, label="start")
    ax.scatter([traj.x[-1]], [traj.y[-1]], c="red", s=40, zorder=5, label="end")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title("Trajectory (bird's-eye)")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=9)

    # Panel 2 — steering angle
    ax = axes[0, 1]
    ax.plot(traj.t, np.degrees(traj.delta), lw=1.4, label="delta (input)")
    ax.set_xlabel("t [s]")
    ax.set_ylabel("delta [deg]")
    ax.set_title("Steering angle (road wheel)")
    ax.grid(True, alpha=0.3)
    ax.axhline(0, color="black", lw=0.5)

    # Panel 3 — longitudinal acceleration
    ax = axes[1, 0]
    ax.plot(traj.t, inp.a, lw=1.4)
    ax.set_xlabel("t [s]")
    ax.set_ylabel("a [m/s²]")
    ax.set_title("Longitudinal acceleration (input)")
    ax.grid(True, alpha=0.3)
    ax.axhline(0, color="black", lw=0.5)

    # Panel 4 — speed
    ax = axes[1, 1]
    ax.plot(traj.t, traj.v, lw=1.4)
    ax.set_xlabel("t [s]")
    ax.set_ylabel("v [m/s]")
    ax.set_title("Speed (state)")
    ax.grid(True, alpha=0.3)

    # Panel 5 — yaw rate
    ax = axes[2, 0]
    ax.plot(traj.t, np.degrees(traj.psi_dot), lw=1.4)
    ax.set_xlabel("t [s]")
    ax.set_ylabel("psi_dot [deg/s]")
    ax.set_title("Yaw rate — KS prediction\n(this is what we will compare to gyro_z from the rlog)")
    ax.grid(True, alpha=0.3)
    ax.axhline(0, color="black", lw=0.5)

    # Panel 6 — lateral acceleration
    ax = axes[2, 1]
    ax.plot(traj.t, traj.a_y, lw=1.4)
    ax.set_xlabel("t [s]")
    ax.set_ylabel("a_y [m/s²]")
    ax.set_title("Lateral acceleration — KS prediction\n(compare to accel_y from the rlog)")
    ax.grid(True, alpha=0.3)
    ax.axhline(0, color="black", lw=0.5)
    # Mark the linear-tyre honesty band (±5 m/s² per the vehicle-tesla-model-3.md regime)
    ax.axhspan(-5.0, 5.0, color="green", alpha=0.06, label="ST linear-honest band (±5 m/s²)")
    ax.legend(loc="best", fontsize=9)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out_path = OUT_DIR / "ks_synthetic.png"
    fig.savefig(out_path, dpi=130)
    print(f"Wrote {out_path}")

    # ---- Print a summary the calibration engineer would want -----------------
    print()
    print("Summary (KS predictions on synthetic drive):")
    print(f"  duration               : {traj.t[-1]:.1f} s")
    print(f"  peak |delta|           : {np.degrees(np.abs(traj.delta)).max():.2f}° (road wheel)")
    print(f"  peak |psi_dot|         : {np.degrees(np.abs(traj.psi_dot)).max():.2f}°/s")
    print(f"  peak |a_y|             : {np.abs(traj.a_y).max():.2f} m/s²")
    print(f"  peak |a_y| within ST   : {'yes' if np.abs(traj.a_y).max() < 5.0 else 'NO — STD needed'}")
    print(f"  final speed            : {traj.v[-1]:.2f} m/s")
    print(f"  net heading change     : {np.degrees(traj.psi[-1] - traj.psi[0]):.1f}°")


if __name__ == "__main__":
    main()
