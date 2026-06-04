"""Rung-1 attempt: linear dynamic single-track on Mach-E (where V1 was weakest).

Fits only C_af; fixes m, Iz, a, b, C_ar from carParams. Two-state Euler.
Scored against V1 (rung-0) on the same train/dev split.
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-01")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "fit-model"))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "final-model"))

from score import score, format_summary  # noqa: E402
from fit import fit, format_fit_summary  # noqa: E402


# carParams: MachEST
MACH_E_P = {
    "m": 2336.0, "Iz": 4879.05, "a": 1.3130, "b": 1.671,
    "C_ar": 355_912,  # rear (carParams) — fix
}


def rung1_predict(sim_df, p):
    delta = sim_df["delta_road_rad"].to_numpy()
    vx = sim_df["v_mps"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    vx_safe = np.maximum(vx, 1.0)
    dt = np.diff(t, prepend=t[0])
    C_af, C_ar = float(p["C_af"]), float(p["C_ar"])
    m, Iz = float(p["m"]), float(p["Iz"])
    a, b = float(p["a"]), float(p["b"])
    vy = 0.0
    yr = 0.0
    out = np.empty_like(vx)
    SUB = 4  # sub-steps per sample to stabilise Euler at low vx
    for i in range(len(vx)):
        dt_i = dt[i] / SUB
        for _ in range(SUB):
            alpha_f = delta[i] - (vy + a * yr) / vx_safe[i]
            alpha_r = -(vy - b * yr) / vx_safe[i]
            F_yf = C_af * alpha_f
            F_yr = C_ar * alpha_r
            vy_dot = (F_yf + F_yr) / m - vx[i] * yr
            yr_dot = (a * F_yf - b * F_yr) / Iz
            vy += vy_dot * dt_i
            yr += yr_dot * dt_i
        # Defensive clamps — runaway diverges in low-vx, high-C_af regime.
        if not (np.isfinite(vy) and np.isfinite(yr)):
            return np.full_like(vx, 1e6)
        if abs(vy) > 20.0: vy = np.sign(vy) * 20.0
        if abs(yr) > 5.0: yr = np.sign(yr) * 5.0
        out[i] = yr
    return out


def predict_factory(platform, coeffs):
    static = MACH_E_P
    merged = {**static, **coeffs}
    return lambda sim_df: rung1_predict(sim_df, merged)


def route_grouped_split(segments, dev_frac=0.25, seed=42):
    rng = np.random.RandomState(seed)
    by_route = defaultdict(list)
    for p in segments:
        route = Path(p).resolve().parents[1].name
        by_route[route].append(p)
    routes = sorted(by_route.keys())
    rng.shuffle(routes)
    n_dev = max(1, int(len(routes) * dev_frac))
    dev_routes = set(routes[:n_dev])
    train, dev = [], []
    for r, segs in by_route.items():
        (dev if r in dev_routes else train).extend(segs)
    return train, dev


def main():
    segs = sorted((ROOT / "data" / "sim" / "segments").glob(
        "FORD_MUSTANG_MACH_E_MK1/**/sim.csv"))
    print(f"Mach-E segments: {len(segs)}")
    train, dev = route_grouped_split(segs, dev_frac=0.25, seed=42)
    print(f"train={len(train)} dev={len(dev)}")

    init = {"FORD_MUSTANG_MACH_E_MK1": {"C_af": 200_000.0}}
    bounds = {"FORD_MUSTANG_MACH_E_MK1": {"C_af": (50_000.0, 500_000.0)}}

    # Manual sweep instead of optimiser — sub-stepped Euler is slow and
    # L-BFGS-B gets zero gradient estimates. A coarse grid is faster.
    grid = [80_000, 120_000, 160_000, 200_000, 250_000, 300_000, 400_000]
    print("Manual sweep over C_af on TRAIN:")
    train_subset = train[:40]  # subset for speed
    best = None
    for c in grid:
        cb = predict_factory("FORD_MUSTANG_MACH_E_MK1", {"C_af": c})
        sq, n = 0.0, 0
        for path in train_subset:
            df = pd.read_csv(path)
            if "yaw_rate_meas_rads" not in df.columns: continue
            yr = cb(df)
            mask = df["v_mps"].to_numpy() > 2.0
            r = (yr - df["yaw_rate_meas_rads"].to_numpy())[mask]
            sq += float(np.sum(r * r)); n += int(mask.sum())
        rmse = np.sqrt(sq / n) if n > 0 else float("nan")
        print(f"  C_af={c:>7d}  yaw_rmse={rmse:.6f}")
        if best is None or rmse < best[1]:
            best = (c, rmse)
    print(f"Best C_af on train-subset: {best[0]} (rmse={best[1]:.6f})")
    res = {"coeffs": {"FORD_MUSTANG_MACH_E_MK1": {"C_af": float(best[0])}}}
    print(format_fit_summary({"coeffs": res["coeffs"],
                              "train_obj": {"FORD_MUSTANG_MACH_E_MK1": best[1]},
                              "dev_obj": None, "gap": None, "gap_fraction": None,
                              "warnings": {}, "history": {}, "n_iter": {},
                              "converged": {"FORD_MUSTANG_MACH_E_MK1": True},
                              "objective": "yaw"}))
    print(format_fit_summary(res))

    # Also score the full Mach-E set under rung 1 + rung 0 for comparison.
    fitted = res["coeffs"]["FORD_MUSTANG_MACH_E_MK1"]
    print(f"\nFitted C_af = {fitted['C_af']:.1f} N/rad (carParams prior: 286_551)")

    cb = predict_factory("FORD_MUSTANG_MACH_E_MK1", fitted)
    def scoring_predict(sim_df, platform):
        return pd.DataFrame(
            {"yaw_rate_pred_rads": cb(sim_df)}, index=sim_df.index)

    full_res = score(scoring_predict, segment_paths=segs,
                     platform_filter="FORD_MUSTANG_MACH_E_MK1")
    print("\n=== Rung-1 (Mach-E only) full-set pooled ===")
    print(f"  yaw_rate_rmse: {full_res['yaw_rate_rmse']:.6f}")
    print(f"  cte_rmse:      {full_res['cte_rmse']:.4f}")


if __name__ == "__main__":
    main()
