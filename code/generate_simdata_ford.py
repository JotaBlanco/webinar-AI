"""Run the KS model on real Ford rlog inputs and write one CSV per segment.

Sibling to generate_simdata.py (which targets TESLA_MODEL_3). Handles both Ford
platforms in commaCarSegments — they share `ford_lincoln_base_pt.dbc`, so the
only thing that changes per platform is the parameter object.

Default behaviour: process 2 segments from each of FORD_MUSTANG_MACH_E_MK1 and
FORD_F_150_LIGHTNING_MK1. Override via CLI:

    python generate_simdata_ford.py                          # both Fords, 2 each
    python generate_simdata_ford.py FORD_MUSTANG_MACH_E_MK1  # Mach-E only
    python generate_simdata_ford.py FORD_F_150_LIGHTNING_MK1 # F-150 only

Per-platform output: KB003/data/sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv

CSV columns (at 50 Hz) — note the truth columns Tesla rlogs cannot supply:

  t_s                      seconds since start of (cropped) segment
  --- DECODED FROM CAN -----------------------------------------------------
  delta_wheel_deg          SteeringPinion_Data.StePinComp_An_Est
  delta_road_rad           delta_wheel_deg · π/180 / steerRatio   (= KS input δ)
  v_mps                    BrakeSysFeatures.Veh_V_ActlBrk (kph) → m/s
  a_long_mps2              BrakeSnData_3.VehLongComp_A_Actl (low-passed 5 Hz)
  a_lat_meas_mps2          BrakeSnData_3.VehLatComp_A_Actl  (low-passed 5 Hz) ← TRUTH
  yaw_rate_meas_rads       Yaw_Data_FD1.VehYaw_W_Actl                         ← TRUTH
  accel_pedal_pct          EngVehicleSpThrottle.ApedPos_Pc_ActlArb
  brake_pressed            EngBrakeData.BpedDrvAppl_D_Actl == 2
  --- KS MODEL OUTPUTS -----------------------------------------------------
  x_m, y_m                 integrated planar position
  psi_rad                  heading
  v_state_mps              v as integrated state (≈ v_mps by construction)
  delta_state_rad          delta as state (clamped to measured)
  yaw_rate_pred_rads       derived: (v/L)·tan(δ)
  a_y_pred_mps2            derived: v·yaw_rate_pred
  --- RESIDUALS (the workshop's payload) -----------------------------------
  yaw_rate_resid_rads      measured − predicted
  a_y_resid_mps2           measured − predicted
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from adapter_ford_rlog import load_segment_measurements
from ks_model import KSDriverInputs, KSState, simulate_ks
from parameters import PARAM_BY_PLATFORM


KB003 = Path(__file__).resolve().parents[1]
DATA_BASE = KB003 / "data" / "raw" / "segments"
SIM_BASE  = KB003 / "data" / "sim" / "segments"

FORD_PLATFORMS = ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1")


def pick_segments(platform: str, n: int) -> list[Path]:
    """Pick n segments, one each from the first n devices. Within a device,
    pick the first non-trivial segment in the first route — reproducible."""
    root = DATA_BASE / platform
    if not root.is_dir():
        raise RuntimeError(f"No data tree for {platform} at {root}")
    devices = sorted([d for d in root.iterdir() if d.is_dir()])
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
            chose = False
            for idx in idxs:
                rlog = idx / "rlog.zst"
                if rlog.exists() and rlog.stat().st_size > 200_000:
                    picks.append(rlog)
                    chose = True
                    break
            if chose:
                break
    return picks[:n]


def run_one(rlog_path: Path, platform: str) -> Path | None:
    p = PARAM_BY_PLATFORM[platform]
    data_root = DATA_BASE / platform
    sim_root  = SIM_BASE  / platform
    rel = rlog_path.parent.relative_to(data_root)
    out_dir = sim_root / rel
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "sim.csv"

    tag = f"{platform}/.../{rel.parts[0][:8]}/.../{rel.parts[-1]}"
    print(f"[{tag}]  decoding…")
    try:
        meas = load_segment_measurements(rlog_path, steer_ratio=p.i_s,
                                         sample_rate_hz=50.0)
    except Exception as e:
        print(f"   ! decode failed: {e}")
        return None

    dt = float(meas.t[1] - meas.t[0])
    delta_dot = np.gradient(meas.delta_road_rad, dt)

    inputs = KSDriverInputs(
        t=meas.t,
        delta_dot=delta_dot,
        a=meas.a_long_mps2,                   # kept in CSV as auxiliary channel
        delta_meas=meas.delta_road_rad,
        v_meas=meas.v_mps,
    )
    initial = KSState(
        x=0.0, y=0.0, psi=0.0,
        v=float(meas.v_mps[0]),
        delta=float(meas.delta_road_rad[0]),
    )
    traj = simulate_ks(
        inputs, initial, p,
        clamp_delta_to_measured=True,
        clamp_v_to_measured=True,            # workshop: speed-known lateral-only
    )

    yaw_resid = meas.yaw_rate_rads - traj.psi_dot
    ay_resid  = meas.a_lat_mps2   - traj.a_y

    headers = [
        "t_s",
        "delta_wheel_deg", "delta_road_rad", "v_mps", "a_long_mps2",
        "a_lat_meas_mps2", "yaw_rate_meas_rads",
        "accel_pedal_pct", "brake_pressed",
        "x_m", "y_m", "psi_rad", "v_state_mps", "delta_state_rad",
        "yaw_rate_pred_rads", "a_y_pred_mps2",
        "yaw_rate_resid_rads", "a_y_resid_mps2",
    ]
    cols = np.column_stack([
        traj.t,
        meas.delta_wheel_deg, meas.delta_road_rad, meas.v_mps, meas.a_long_mps2,
        meas.a_lat_mps2, meas.yaw_rate_rads,
        meas.accel_pedal_pct, meas.brake_pressed,
        traj.x, traj.y, traj.psi, traj.v, traj.delta,
        traj.psi_dot, traj.a_y,
        yaw_resid, ay_resid,
    ])
    assert cols.shape == (len(traj.t), len(headers))

    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for row in cols:
            w.writerow([f"{x:.6g}" for x in row])

    # RMS residual is the headline number for the workshop
    yaw_rms_degs = np.degrees(np.sqrt(np.mean(yaw_resid ** 2)))
    ay_rms       = np.sqrt(np.mean(ay_resid ** 2))
    print(f"   → {out_csv.relative_to(KB003)}")
    print(f"     N={len(traj.t)}  v∈[{meas.v_mps.min():.1f},{meas.v_mps.max():.1f}] m/s  "
          f"|ψ̇_meas|max={np.degrees(np.abs(meas.yaw_rate_rads)).max():.1f}°/s  "
          f"|a_y_meas|max={np.abs(meas.a_lat_mps2).max():.2f} m/s²")
    print(f"     RMS residual ψ̇ = {yaw_rms_degs:.3f} °/s   "
          f"RMS residual a_y = {ay_rms:.3f} m/s²")
    return out_csv


def write_manifest(platform: str, written: list[Path]) -> Path:
    sim_root = SIM_BASE / platform
    sim_root.mkdir(parents=True, exist_ok=True)
    items = []
    for csvp in written:
        rel = csvp.parent.relative_to(sim_root)
        parts = rel.parts  # device / route / idx
        items.append({
            "device": parts[0],
            "route":  parts[1],
            "idx":    parts[2],
            "csv_path": f"segments/{platform}/{rel.as_posix()}/sim.csv",
            "rows": sum(1 for _ in open(csvp)) - 1,
        })
    manifest = {
        "platform": platform,
        "generator": "code/generate_simdata_ford.py",
        "model": "CommonRoad KS (kinematic single-track), speed-known lateral-only",
        "input_contract": {
            "v_clamped_to_measured": True,
            "delta_clamped_to_measured": True,
            "predicted": ["psi", "psi_dot", "a_y", "x", "y"],
        },
        "parameter_source": "openpilot Ford interface (carParams)",
        "truth_channels": ["yaw_rate_meas_rads (Yaw_Data_FD1.VehYaw_W_Actl)",
                           "a_lat_meas_mps2 (BrakeSnData_3.VehLatComp_A_Actl)"],
        "sample_rate_hz": 50,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "segments": items,
    }
    out = sim_root / "manifest.json"
    with open(out, "w") as f:
        json.dump(manifest, f, indent=2)
    return out


def process_platform(platform: str, n: int = 2) -> list[Path]:
    print(f"\n=== {platform} ===")
    rlogs = pick_segments(platform, n)
    print(f"Selected {len(rlogs)} segments:")
    for p in rlogs:
        print(f"  {p.relative_to(KB003)}")
    written: list[Path] = []
    for rlog in rlogs:
        out = run_one(rlog, platform)
        if out is not None:
            written.append(out)
    if written:
        mp = write_manifest(platform, written)
        print(f"\nWrote {len(written)} CSVs + manifest: {mp.relative_to(KB003)}")
    return written


def main():
    if len(sys.argv) >= 2:
        targets = [sys.argv[1]]
    else:
        targets = list(FORD_PLATFORMS)
    for plat in targets:
        if plat not in FORD_PLATFORMS:
            print(f"unknown platform: {plat}", file=sys.stderr)
            sys.exit(2)
        process_platform(plat, n=2)


if __name__ == "__main__":
    main()
