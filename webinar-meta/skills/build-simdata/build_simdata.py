#!/usr/bin/env python3
"""Decode rlog -> KS-baseline sim.csv -> truth-stripped sim-only.csv.

Replaces the per-OEM generate_simdata_*.py scripts. One CLI; dispatches by
platform name to the correct adapter; processes both train (data_root) and
val (val_data_root) trees by default; writes the parallel sim-only/ tree
that the grader and the agents read.

Layout (paths from webinar-meta/data-paths.json):

  <root>/raw/segments/<PLATFORM>/<dev>/<route>/<idx>/rlog.zst   ← input
  <root>/sim/segments/<PLATFORM>/<dev>/<route>/<idx>/sim.csv    ← full output
  <root>/sim-only/segments/<PLATFORM>/...sim.csv                ← truth-stripped

Usage:
    python build_simdata.py                    # discovery view (no work)
    python build_simdata.py HYUNDAI_IONIQ_5    # both sides, all segments, sim + sim-only
    python build_simdata.py TESLA_MODEL_3 --side train --limit 6
    python build_simdata.py FORD_MUSTANG_MACH_E_MK1 --no-sim-only
    python build_simdata.py --refresh-sim-only HYUNDAI_IONIQ_5   # regenerate sim-only/ from existing sim/
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

# Skill layout: this script is at webinar-meta/skills/build-simdata/.
# code/ lives at <repo>/code; _adapters/ at <skill>/_adapters/.
SKILL_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILL_DIR.parents[2]
CODE_DIR  = REPO_ROOT / "code"
ADAPTERS_DIR = SKILL_DIR / "_adapters"

# Make code/ (rlog_reader, ks_model, parameters) and _adapters/ importable.
for p in (CODE_DIR, ADAPTERS_DIR):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import numpy as np                                      # noqa: E402
from ks_model import KSDriverInputs, KSState, simulate_ks  # noqa: E402
from parameters import PARAM_BY_PLATFORM                # noqa: E402


def load_data_paths():
    cfg = REPO_ROOT / "webinar-meta" / "data-paths.json"
    if not cfg.exists():
        sys.exit(f"missing {cfg}")
    return json.loads(cfg.read_text())


# -----------------------------------------------------------------------------
# Per-OEM segment builders
# -----------------------------------------------------------------------------
#
# Each builder takes (rlog_path, platform) and returns (headers, cols) where
# cols is a 2-D ndarray with shape (N, len(headers)). The dispatcher writes
# the CSV, accumulates metrics, and runs the sim-only projection.

def _build_tesla(rlog_path: Path, platform: str):
    from adapter_tesla_rlog import load_segment_measurements
    p = PARAM_BY_PLATFORM[platform]
    meas = load_segment_measurements(rlog_path, sample_rate_hz=50.0)
    dt = float(meas.t[1] - meas.t[0])
    delta_dot = np.gradient(meas.delta_road_rad, dt)
    inputs = KSDriverInputs(t=meas.t, delta_dot=delta_dot, a=meas.a_long_mps2,
                            delta_meas=meas.delta_road_rad, v_meas=meas.v_mps)
    initial = KSState(x=0.0, y=0.0, psi=0.0,
                      v=float(meas.v_mps[0]),
                      delta=float(meas.delta_road_rad[0]))
    traj = simulate_ks(inputs, initial, p,
                       clamp_delta_to_measured=True, clamp_v_to_measured=True)
    headers = [
        "t_s",
        "delta_wheel_deg", "delta_road_rad", "v_mps", "a_long_mps2",
        "accel_pedal_pct", "brake_pedal_state", "di_torque_actual_nm",
        "wheel_FL_kph", "wheel_FR_kph", "wheel_RL_kph", "wheel_RR_kph",
        "x_m", "y_m", "psi_rad", "v_state_mps", "delta_state_rad",
        "psi_dot_rads", "a_y_mps2",
    ]
    cols = np.column_stack([
        traj.t,
        meas.delta_wheel_deg, meas.delta_road_rad, meas.v_mps, meas.a_long_mps2,
        meas.accel_pedal_pct, meas.brake_pedal_state, meas.di_torque_actual_nm,
        meas.wheel_speeds_kph[:, 0], meas.wheel_speeds_kph[:, 1],
        meas.wheel_speeds_kph[:, 2], meas.wheel_speeds_kph[:, 3],
        traj.x, traj.y, traj.psi, traj.v, traj.delta,
        traj.psi_dot, traj.a_y,
    ])
    return headers, cols


def _build_ford(rlog_path: Path, platform: str):
    from adapter_ford_rlog import load_segment_measurements
    p = PARAM_BY_PLATFORM[platform]
    meas = load_segment_measurements(rlog_path, steer_ratio=p.i_s, sample_rate_hz=50.0)
    dt = float(meas.t[1] - meas.t[0])
    delta_dot = np.gradient(meas.delta_road_rad, dt)
    inputs = KSDriverInputs(t=meas.t, delta_dot=delta_dot, a=meas.a_long_mps2,
                            delta_meas=meas.delta_road_rad, v_meas=meas.v_mps)
    initial = KSState(x=0.0, y=0.0, psi=0.0,
                      v=float(meas.v_mps[0]),
                      delta=float(meas.delta_road_rad[0]))
    traj = simulate_ks(inputs, initial, p,
                       clamp_delta_to_measured=True, clamp_v_to_measured=True)
    yaw_resid = meas.yaw_rate_rads - traj.psi_dot
    ay_resid  = meas.a_lat_mps2    - traj.a_y
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
    return headers, cols


def _build_hyundai(rlog_path: Path, platform: str):
    from adapter_hyundai_rlog import load_segment_measurements
    p = PARAM_BY_PLATFORM[platform]
    meas = load_segment_measurements(rlog_path, steer_ratio=p.i_s, sample_rate_hz=50.0)
    dt = float(meas.t[1] - meas.t[0])
    delta_dot = np.gradient(meas.delta_road_rad, dt)
    inputs = KSDriverInputs(t=meas.t, delta_dot=delta_dot, a=meas.a_long_mps2,
                            delta_meas=meas.delta_road_rad, v_meas=meas.v_mps)
    initial = KSState(x=0.0, y=0.0, psi=0.0,
                      v=float(meas.v_mps[0]),
                      delta=float(meas.delta_road_rad[0]))
    traj = simulate_ks(inputs, initial, p,
                       clamp_delta_to_measured=True, clamp_v_to_measured=True)
    yaw_resid = meas.yaw_rate_rads - traj.psi_dot
    ay_resid  = meas.a_lat_mps2    - traj.a_y
    headers = [
        "t_s",
        "delta_wheel_deg", "delta_road_rad", "v_mps", "a_long_mps2",
        "a_lat_meas_mps2", "yaw_rate_meas_rads", "steer_rate_dps",
        "x_m", "y_m", "psi_rad", "v_state_mps", "delta_state_rad",
        "yaw_rate_pred_rads", "a_y_pred_mps2",
        "yaw_rate_resid_rads", "a_y_resid_mps2",
    ]
    cols = np.column_stack([
        traj.t,
        meas.delta_wheel_deg, meas.delta_road_rad, meas.v_mps, meas.a_long_mps2,
        meas.a_lat_mps2, meas.yaw_rate_rads, meas.steer_rate_dps,
        traj.x, traj.y, traj.psi, traj.v, traj.delta,
        traj.psi_dot, traj.a_y,
        yaw_resid, ay_resid,
    ])
    return headers, cols


# OEM-prefix → (builder function, sim-only column map).
# To add a new OEM: drop an adapter into _adapters/, add a builder above,
# register it here, and add a sim-only mapping below.
Builder = Callable[[Path, str], tuple[list[str], "np.ndarray"]]

BUILDERS: dict[str, Builder] = {
    "TESLA":   _build_tesla,
    "FORD":    _build_ford,
    "HYUNDAI": _build_hyundai,
    "KIA":     _build_hyundai,    # E-GMP cousins share the canfd DBC
    "GENESIS": _build_hyundai,    # E-GMP cousins share the canfd DBC
}


# -----------------------------------------------------------------------------
# sim-only projection (8-column agent-facing schema)
# -----------------------------------------------------------------------------

SIM_ONLY_HEADERS = [
    "t_s", "delta_wheel_deg", "delta_road_rad", "v_mps", "a_long_mps2",
    "accel_pedal_pct", "brake_pressed", "yaw_rate_pred_rads",
]


def _tesla_brake_bool(s: str) -> str:
    """Tesla brake_pedal_state >2 -> 1, else 0. (Encoding has 2 as idle.)"""
    try:
        return "1" if float(s) > 2 else "0"
    except (TypeError, ValueError):
        return ""


# target_col -> (source_col_in_sim.csv, optional_transform). None source => emit empty.
SIM_ONLY_MAPS = {
    "TESLA": {
        "t_s":                ("t_s",                None),
        "delta_wheel_deg":    ("delta_wheel_deg",    None),
        "delta_road_rad":     ("delta_road_rad",     None),
        "v_mps":              ("v_mps",              None),
        "a_long_mps2":        ("a_long_mps2",        None),
        "accel_pedal_pct":    ("accel_pedal_pct",    None),
        "brake_pressed":      ("brake_pedal_state",  _tesla_brake_bool),
        "yaw_rate_pred_rads": ("psi_dot_rads",       None),
    },
    "FORD": {c: (c, None) for c in SIM_ONLY_HEADERS},
    "HYUNDAI": {
        "t_s":                ("t_s",                None),
        "delta_wheel_deg":    ("delta_wheel_deg",    None),
        "delta_road_rad":     ("delta_road_rad",     None),
        "v_mps":              ("v_mps",              None),
        "a_long_mps2":        ("a_long_mps2",        None),
        "accel_pedal_pct":    (None,                 None),  # not on E-GMP CAN-FD
        "brake_pressed":      (None,                 None),  # not on E-GMP CAN-FD
        "yaw_rate_pred_rads": ("yaw_rate_pred_rads", None),
    },
}
SIM_ONLY_MAPS["KIA"]     = SIM_ONLY_MAPS["HYUNDAI"]
SIM_ONLY_MAPS["GENESIS"] = SIM_ONLY_MAPS["HYUNDAI"]


def project_sim_only(sim_csv: Path, sim_only_csv: Path, oem: str):
    mapping = SIM_ONLY_MAPS[oem]
    sim_only_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(sim_csv) as fin, open(sim_only_csv, "w", newline="") as fout:
        r = csv.DictReader(fin)
        w = csv.writer(fout)
        w.writerow(SIM_ONLY_HEADERS)
        for row in r:
            out = []
            for target in SIM_ONLY_HEADERS:
                src_col, transform = mapping[target]
                if src_col is None:
                    out.append("")
                else:
                    val = row.get(src_col, "")
                    out.append(transform(val) if transform else val)
            w.writerow(out)


# -----------------------------------------------------------------------------
# Driver
# -----------------------------------------------------------------------------

def oem_of(platform: str) -> str:
    return platform.split("_", 1)[0].upper()


def _process_segment(args):
    """Worker — runs in a subprocess so per-segment cantools/numpy state is isolated."""
    rlog_path, platform, sim_csv, sim_only_csv = args
    rlog_path = Path(rlog_path); sim_csv = Path(sim_csv)
    builder = BUILDERS[oem_of(platform)]
    sim_csv.parent.mkdir(parents=True, exist_ok=True)
    if sim_csv.exists() and sim_csv.stat().st_size > 0:
        status = "skip"
    else:
        headers, cols = builder(rlog_path, platform)
        with open(sim_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for row in cols:
                w.writerow([f"{x:.6g}" for x in row])
        status = "ok"
    if sim_only_csv is not None:
        sim_only_csv = Path(sim_only_csv)
        if not (sim_only_csv.exists() and sim_only_csv.stat().st_size > 0):
            project_sim_only(sim_csv, sim_only_csv, oem_of(platform))
    return (status, str(sim_csv))


def collect_rlogs(raw_root: Path, platform: str, limit: int | None):
    plat_dir = raw_root / "raw" / "segments" / platform
    if not plat_dir.is_dir():
        return []
    rlogs = []
    for rlog in sorted(plat_dir.rglob("rlog.zst")):
        if rlog.stat().st_size > 200_000:
            rlogs.append(rlog)
            if limit and len(rlogs) >= limit:
                break
    return rlogs


def build_side(side_label: str, root: Path, platform: str,
               limit: int | None, workers: int, write_sim_only: bool):
    rlogs = collect_rlogs(root, platform, limit)
    if not rlogs:
        return None
    raw_base = root / "raw" / "segments" / platform
    sim_base = root / "sim" / "segments" / platform
    so_base  = root / "sim-only" / "segments" / platform

    jobs = []
    for rlog in rlogs:
        rel = rlog.parent.relative_to(raw_base)
        sim_csv = sim_base / rel / "sim.csv"
        so_csv = (so_base / rel / "sim.csv") if write_sim_only else None
        jobs.append((str(rlog), platform, str(sim_csv), str(so_csv) if so_csv else None))

    print(f"\n[{side_label}] {platform}: {len(jobs)} segments  "
          f"raw={raw_base.relative_to(REPO_ROOT)}  sim={sim_base.relative_to(REPO_ROOT)}")
    t0 = time.time()
    ok = skip = err = 0
    errors = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_process_segment, j) for j in jobs]
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                status, path = fut.result()
                if status == "ok":
                    ok += 1
                else:
                    skip += 1
            except Exception as e:
                err += 1
                errors.append(str(e))
            if i % 25 == 0 or i == len(jobs):
                el = time.time() - t0
                rate = i / el if el > 0 else 0
                print(f"  [{side_label} {i:4d}/{len(jobs)}] ok={ok} skip={skip} err={err}  "
                      f"({rate:.1f} seg/s, {el:.0f}s)")
    if errors:
        print(f"  [{side_label} warn] first error: {errors[0]}")
    return {"ok": ok, "skip": skip, "err": err, "n": len(jobs)}


def write_manifest(root: Path, platform: str, totals_per_side: dict):
    sim_dir = root / "sim" / "segments" / platform
    if not sim_dir.is_dir():
        return
    csvs = list(sim_dir.rglob("sim.csv"))
    manifest = {
        "platform": platform,
        "generator": "webinar-meta/skills/build-simdata/build_simdata.py",
        "model": "CommonRoad KS (kinematic single-track), speed-known lateral-only",
        "input_contract": {"v_clamped_to_measured": True, "delta_clamped_to_measured": True},
        "sample_rate_hz": 50,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "totals": totals_per_side,
        "n_segments_on_disk": len(csvs),
    }
    out = sim_dir / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2))
    print(f"  wrote {out.relative_to(REPO_ROOT)}")


def render_discovery(paths):
    print(f"# build-simdata — discovery (no work performed)\n")
    print(f"  data_root:     {(REPO_ROOT / paths['data_root']).resolve()}")
    print(f"  val_data_root: {(REPO_ROOT / paths['val_data_root']).resolve()}\n")
    for label, key in [("TRAIN", "data_root"), ("VAL", "val_data_root")]:
        root = REPO_ROOT / paths[key]
        raw_root = root / "raw" / "segments"
        sim_root = root / "sim" / "segments"
        so_root  = root / "sim-only" / "segments"
        print(f"## {label}  ({raw_root.relative_to(REPO_ROOT)})\n")
        if not raw_root.is_dir():
            print("  (raw/ tree is empty)\n")
            continue
        rows = []
        for plat_dir in sorted(p for p in raw_root.iterdir() if p.is_dir()):
            plat = plat_dir.name
            n_raw = sum(1 for _ in plat_dir.rglob("rlog.zst"))
            n_sim = sum(1 for _ in (sim_root / plat).rglob("sim.csv")) if (sim_root / plat).exists() else 0
            n_so  = sum(1 for _ in (so_root  / plat).rglob("sim.csv")) if (so_root  / plat).exists() else 0
            adapter_ok = "✓" if oem_of(plat) in BUILDERS else "✗ no adapter"
            rows.append((plat, n_raw, n_sim, n_so, adapter_ok))
        if not rows:
            print("  (no platforms)\n"); continue
        widths = [max(len(str(r[i])) for r in [("Platform", "raw", "sim", "sim-only", "adapter")] + rows)
                  for i in range(5)]
        fmt = "  " + "  ".join(f"{{:<{w}}}" for w in widths)
        print(fmt.format("Platform", "raw", "sim", "sim-only", "adapter"))
        print(fmt.format(*["-"*w for w in widths]))
        for r in rows:
            print(fmt.format(*r))
        print()
    print("Next: build_simdata.py <PLATFORM>   # processes both sides, full pass.")


def refresh_sim_only(platform: str, paths):
    """Regenerate sim-only/ from existing sim/. Useful after a sim-only schema bump."""
    if oem_of(platform) not in SIM_ONLY_MAPS:
        sys.exit(f"unknown platform {platform!r}")
    n_ok = n_skip = 0
    for key in ("data_root", "val_data_root"):
        root = REPO_ROOT / paths[key]
        sim_root = root / "sim" / "segments" / platform
        so_root  = root / "sim-only" / "segments" / platform
        if not sim_root.is_dir():
            continue
        for sim_csv in sim_root.rglob("sim.csv"):
            rel = sim_csv.relative_to(sim_root)
            so_csv = so_root / rel
            so_csv.parent.mkdir(parents=True, exist_ok=True)
            project_sim_only(sim_csv, so_csv, oem_of(platform))
            n_ok += 1
    print(f"refreshed sim-only/ for {platform}: {n_ok} files")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("platform", nargs="?", help="Platform id (e.g. FORD_F_150_LIGHTNING_MK1). Omit for discovery view.")
    ap.add_argument("--side", choices=["train", "val", "both"], default="both")
    ap.add_argument("--limit", type=int, default=None, help="Only build the first N segments (per side). For smoke tests.")
    ap.add_argument("--no-sim-only", action="store_true", help="Skip sim-only/ projection.")
    ap.add_argument("--refresh-sim-only", action="store_true", help="Rebuild sim-only/ from existing sim/, no decoding.")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    paths = load_data_paths()

    if args.platform is None:
        render_discovery(paths)
        return

    if oem_of(args.platform) not in BUILDERS:
        sys.exit(f"no adapter registered for OEM {oem_of(args.platform)!r}. "
                 f"Known: {sorted(BUILDERS)}. Add one in _adapters/ + BUILDERS dict.")
    if args.platform not in PARAM_BY_PLATFORM:
        sys.exit(f"no parameter set for {args.platform!r} in code/parameters.py. "
                 f"Known: {sorted(PARAM_BY_PLATFORM)}.")

    if args.refresh_sim_only:
        refresh_sim_only(args.platform, paths)
        return

    sides = []
    if args.side in ("train", "both"):
        sides.append(("train", REPO_ROOT / paths["data_root"]))
    if args.side in ("val", "both"):
        sides.append(("val",   REPO_ROOT / paths["val_data_root"]))

    totals = {}
    write_so = not args.no_sim_only
    for label, root in sides:
        res = build_side(label, root, args.platform, args.limit, args.workers, write_so)
        if res is not None:
            totals[label] = res

    for label, root in sides:
        if totals.get(label):
            write_manifest(root, args.platform, totals)

    if not totals:
        print("(no segments found on either side)")
        return
    print("\n[done]")
    for label, t in totals.items():
        print(f"  {label}: ok={t['ok']}  skip={t['skip']}  err={t['err']}  total={t['n']}")


if __name__ == "__main__":
    main()
