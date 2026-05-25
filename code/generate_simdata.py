"""Run the KS model on real Tesla rlog inputs and write one CSV per segment.

Selects 6 segments from 6 different devices in KB003/data, decodes each, runs
the KS model forward using the measured steering and derived a_long, and writes:

    KB003/data/sim/segments/TESLA_MODEL_3/<device>/<route>/<idx>/sim.csv

…mirroring the data tree.

CSV columns (at 50 Hz):

  t_s                    seconds since start of (cropped) segment
  --- DECODED FROM RLOG (driver / vehicle measurement) ------------------
  delta_wheel_deg        steering wheel angle (raw decoded)
  delta_road_rad         delta_wheel_deg · π/180 / steerRatio   (= KS input δ)
  v_mps                  DI_vehicleSpeed (kph) → m/s
  a_long_mps2            derived: lowpass(d(v)/dt, 5 Hz)        (= KS input a)
  accel_pedal_pct        DI_accelPedalPos (driver intent only)
  brake_pedal_state      DI_brakePedalState (enum int)
  di_torque_actual_nm    drive-inverter actual torque (for residual analysis)
  --- KS MODEL OUTPUTS --------------------------------------------------
  x_m, y_m               integrated planar position
  psi_rad                heading
  v_state_mps            v as integrated state (≈ v_mps by construction)
  delta_state_rad        delta as state (clamped to measured)
  psi_dot_rads           derived: (v/L)·tan(δ)
  a_y_mps2               derived: v·psi_dot
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from adapter_tesla_rlog import load_segment_measurements
from ks_model import KSDriverInputs, KSState, simulate_ks
from parameters import TESLA_MODEL_3


KB003 = Path(__file__).resolve().parents[1]
DATA_ROOT = KB003 / "data" / "raw" / "segments" / "TESLA_MODEL_3"
SIMDATA_ROOT = KB003 / "data" / "sim" / "segments" / "TESLA_MODEL_3"


def pick_segments(n: int = 6) -> list[Path]:
    """Pick n segments, one from each of the first n devices, choosing the
    first segment within the first route of each device for reproducibility."""
    devices = sorted([d for d in DATA_ROOT.iterdir() if d.is_dir()])
    picks: list[Path] = []
    for dev in devices:
        if len(picks) >= n:
            break
        routes = sorted([r for r in dev.iterdir() if r.is_dir()])
        for route in routes:
            idxs = sorted(
                [p for p in route.iterdir() if p.is_dir()],
                key=lambda p: int(p.name) if p.name.isdigit() else p.name,
            )
            for idx in idxs:
                rlog = idx / "rlog.zst"
                if rlog.exists() and rlog.stat().st_size > 200_000:
                    picks.append(rlog)
                    break
            if len(picks) > len(picks) - 1:  # only one segment per device
                break
    return picks[:n]


def run_one(rlog_path: Path) -> Path:
    rel = rlog_path.parent.relative_to(DATA_ROOT)
    out_dir = SIMDATA_ROOT / rel
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "sim.csv"

    print(f"[{rlog_path.parent.parent.parent.name}/.../{rlog_path.parent.name}]  decoding...")
    meas = load_segment_measurements(rlog_path, sample_rate_hz=50.0)

    # KS inputs: use measured delta as the clamped state, measured a_long as input,
    # delta_dot derived numerically (used only when the integrator falls back to
    # rate mode — we clamp).
    dt = float(meas.t[1] - meas.t[0])
    delta_dot = np.gradient(meas.delta_road_rad, dt)

    inputs = KSDriverInputs(
        t=meas.t,
        delta_dot=delta_dot,
        a=meas.a_long_mps2,
        delta_meas=meas.delta_road_rad,
        v_meas=meas.v_mps,
    )
    initial = KSState(
        x=0.0, y=0.0, psi=0.0,
        v=float(meas.v_mps[0]),
        delta=float(meas.delta_road_rad[0]),
    )
    traj = simulate_ks(
        inputs, initial, TESLA_MODEL_3,
        clamp_delta_to_measured=True,
        clamp_v_to_measured=True,        # workshop: speed-known lateral-only
    )

    # Compose the CSV
    headers = [
        "t_s",
        "delta_wheel_deg", "delta_road_rad", "v_mps", "a_long_mps2",
        "accel_pedal_pct", "brake_pedal_state", "di_torque_actual_nm",
        "wheel_FL_kph", "wheel_FR_kph", "wheel_RL_kph", "wheel_RR_kph",
        "x_m", "y_m", "psi_rad", "v_state_mps", "delta_state_rad",
        "psi_dot_rads", "a_y_mps2",
    ]
    N = len(traj.t)
    cols = np.column_stack([
        traj.t,
        meas.delta_wheel_deg, meas.delta_road_rad, meas.v_mps, meas.a_long_mps2,
        meas.accel_pedal_pct, meas.brake_pedal_state, meas.di_torque_actual_nm,
        meas.wheel_speeds_kph[:, 0], meas.wheel_speeds_kph[:, 1],
        meas.wheel_speeds_kph[:, 2], meas.wheel_speeds_kph[:, 3],
        traj.x, traj.y, traj.psi, traj.v, traj.delta,
        traj.psi_dot, traj.a_y,
    ])
    assert cols.shape == (N, len(headers))

    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for row in cols:
            w.writerow([f"{x:.6g}" for x in row])

    print(f"   → {out_csv.relative_to(KB003)}  ({N} rows, "
          f"v∈[{meas.v_mps.min():.1f},{meas.v_mps.max():.1f}] m/s, "
          f"|psi_dot|max={np.degrees(np.abs(traj.psi_dot)).max():.1f}°/s, "
          f"|a_y|max={np.abs(traj.a_y).max():.2f} m/s²)")
    return out_csv


def write_manifest(written: list[Path]) -> Path:
    """Mirror the data/.../manifest.json pattern with a sim-side manifest."""
    import json
    from datetime import datetime, timezone

    SIMDATA_ROOT.mkdir(parents=True, exist_ok=True)
    items = []
    for csvp in written:
        rel = csvp.parent.relative_to(SIMDATA_ROOT)
        parts = rel.parts  # device / route / idx
        items.append({
            "device": parts[0],
            "route":  parts[1],
            "idx":    parts[2],
            "csv_path": f"segments/TESLA_MODEL_3/{rel.as_posix()}/sim.csv",
            "rows": sum(1 for _ in open(csvp)) - 1,
        })
    manifest = {
        "platform": "TESLA_MODEL_3",
        "generator": "code/generate_simdata.py",
        "model": "CommonRoad KS (kinematic single-track), speed-known lateral-only",
        "input_contract": {
            "v_clamped_to_measured": True,
            "delta_clamped_to_measured": True,
            "predicted": ["psi", "psi_dot", "a_y", "x", "y"],
        },
        "parameter_source": "openpilot Tesla interface (carParams)",
        "sample_rate_hz": 50,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "segments": items,
    }
    out = SIMDATA_ROOT / "manifest.json"
    with open(out, "w") as f:
        json.dump(manifest, f, indent=2)
    return out


def main():
    SIMDATA_ROOT.mkdir(parents=True, exist_ok=True)
    rlogs = pick_segments(6)
    print(f"Selected {len(rlogs)} segments:")
    for p in rlogs:
        print(f"  {p.relative_to(KB003)}")

    written = []
    for rlog in rlogs:
        try:
            written.append(run_one(rlog))
        except Exception as e:
            print(f"  ! skipped {rlog.name}: {e}")
            continue

    if written:
        mp = write_manifest(written)
        print(f"\nWrote {len(written)} CSVs + manifest: {mp.relative_to(KB003)}")


if __name__ == "__main__":
    main()
