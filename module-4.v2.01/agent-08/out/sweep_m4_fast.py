"""Fast per-platform sigma sweep for M4 — loads each segment once.

We bypass score-model's per-call CSV reload by running our own loop, then
finish with a clean score-model dev pass at the chosen sigma per platform.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
M4_DIR = ROOT / "phases/3-implement/models/m4-relaxation-length"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(M4_DIR))

from _shared.frozen_split import train_paths, dev_paths  # noqa: E402
from _shared.physics_core import safe_dt  # noqa: E402
from score import score  # noqa: E402
import model as m4  # noqa: E402

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
V_MIN_M4 = 1.5
V_FILTER = 2.0  # match score-model sample_filter_v_mps
TRUTH_COL = "yaw_rate_meas_rads"


def _per_segment_delta0(sim_df, fallback, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def run_segment(sim_df, p, sigma):
    delta_row = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    dt = safe_dt(t)
    if p["use_per_segment_delta0"]:
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
    else:
        delta0 = p["delta0"]
    delta_eff = (delta_row - delta0) * p["g"]
    yr_demand = v * delta_eff / (p["L_eff"] + p["K_us"] * v * v)
    n = len(t)
    out = np.empty(n)
    out[0] = yr_demand[0] if v[0] >= V_MIN_M4 else yr_v0[0]
    yr_state = out[0]
    for i in range(1, n):
        if v[i] < V_MIN_M4 or sigma <= 0.0:
            yr_state = yr_v0[i]
            out[i] = yr_v0[i]
            continue
        alpha = 1.0 - np.exp(-v[i] * dt[i] / sigma)
        yr_state = yr_state + alpha * (yr_demand[i] - yr_state)
        out[i] = yr_state
    return out


def main():
    train = train_paths()
    dev = dev_paths()
    print(f"train={len(train)} dev={len(dev)}", flush=True)

    grid = [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.65, 0.8, 1.0, 1.25, 1.5, 1.8, 2.2]

    best_per_plat = {}
    sweeps = {}
    for plat in PLATFORMS:
        p = m4.V1_PARAMS[plat]
        plat_train = [pp for pp in train if pp.parts[-5] == plat]
        print(f"\n[{plat}] {len(plat_train)} segments", flush=True)

        # Preload arrays
        loaded = []
        for path in plat_train:
            try:
                df = pd.read_csv(path)
            except Exception:
                continue
            if TRUTH_COL not in df.columns or "v_mps" not in df.columns:
                continue
            v = df["v_mps"].to_numpy()
            truth = df[TRUTH_COL].to_numpy()
            mask = v > V_FILTER
            if mask.sum() < 10:
                continue
            loaded.append((df, truth, mask))
        print(f"  loaded {len(loaded)} segments", flush=True)

        rows = []
        for sigma in grid:
            sum_sq = 0.0
            n_tot = 0
            for df, truth, mask in loaded:
                pred = run_segment(df, p, sigma)
                err = (pred - truth)[mask]
                sum_sq += float(np.dot(err, err))
                n_tot += int(mask.sum())
            rmse = float(np.sqrt(sum_sq / n_tot)) if n_tot else float("inf")
            rows.append({"sigma": sigma, "yaw_rmse": rmse, "n": n_tot})
            print(f"  sigma={sigma:5.2f}  yaw {rmse:.6f}  n={n_tot}", flush=True)
        rows.sort(key=lambda r: r["yaw_rmse"])
        best_per_plat[plat] = {"sigma": rows[0]["sigma"], "train_yaw_rmse": rows[0]["yaw_rmse"]}
        sweeps[plat] = rows

    print(f"\nbest: {best_per_plat}", flush=True)

    # Write coeffs.json
    coeffs = {plat: {"sigma": best_per_plat[plat]["sigma"]} for plat in PLATFORMS}
    coeffs_path = M4_DIR / "coeffs.json"
    with coeffs_path.open("w") as f:
        json.dump(coeffs, f, indent=2)
    print(f"wrote {coeffs_path}", flush=True)

    # Score on dev using score-model for canonical numbers
    print("scoring on dev with chosen sigmas...", flush=True)
    r_dev = score(m4.predict, segment_paths=dev)
    print(f"  M4 dev  yaw {r_dev['yaw_rate_rmse']:.6f}  cte {r_dev['cte_rmse']:.4f}", flush=True)
    for plat, s in r_dev["per_platform"].items():
        print(f"    {plat:30s}  yaw {s.get('yaw_rate_rmse')}  cte {s.get('cte_rmse')}  n={s.get('n_segments')}", flush=True)

    out = {
        "best": best_per_plat,
        "sweeps": sweeps,
        "dev": {
            "yaw_rate_rmse": r_dev["yaw_rate_rmse"],
            "cte_rmse": r_dev["cte_rmse"],
            "per_platform": {k: {kk: v.get(kk) for kk in ("yaw_rate_rmse", "cte_rmse", "n_segments")} for k, v in r_dev["per_platform"].items()},
            "per_regime": r_dev.get("per_regime"),
        },
    }
    out_path = HERE / "m4_sweep.json"
    with out_path.open("w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
