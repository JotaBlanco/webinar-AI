"""Fit per-platform corrections to V0, evaluate on dev split.

Variants:
  V0:    yp                                (baseline)
  V1:    a*yp                              (linear scale)
  V2:    a*yp + b*yp**3                    (cubic compliance)
  V3:    v*delta / (L + K_us*v^2)          (understeer bicycle)
  V4:    a*yp + b*yp*v^2                   (v^2 understeer correction equivalent)
"""
from __future__ import annotations
import sys, glob, json, math, random
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-04")
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "code"))
from traj_metrics import cte_diagnostics_segment  # noqa
import parameters as P_mod  # noqa

TRUTH_COL = {
    "TESLA_MODEL_3": "psi_dot_rads",
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "FORD_MUSTANG_MACH_E_MK1": "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5": "yaw_rate_meas_rads",
}

WHEELBASE = {
    "TESLA_MODEL_3": 2.875,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "HYUNDAI_IONIQ_5": 3.00,  # rough, will be absorbed by fit
}


def _platform(p): return Path(p).resolve().parents[3].name


def load_all():
    """Load all sim.csv with full schema; per-platform truth column normalized to 'yt'."""
    paths = sorted(glob.glob(str(ROOT / "data/sim/segments/*/*/*/*/sim.csv")))
    out = {}
    for p in paths:
        plat = _platform(p)
        out.setdefault(plat, []).append(p)
    return out


def load_seg(p):
    plat = _platform(p)
    df = pd.read_csv(p)
    truth_col = TRUTH_COL[plat]
    if truth_col not in df.columns:
        return None
    df["yt"] = df[truth_col]
    # ensure yaw_rate_pred_rads present
    if "yaw_rate_pred_rads" not in df.columns:
        # Tesla case: use psi_dot_rads as both pred & truth (no info)
        df["yaw_rate_pred_rads"] = df[truth_col]
    if "brake_pressed" not in df.columns and "brake_pedal_state" in df.columns:
        df["brake_pressed"] = (df["brake_pedal_state"] > 0).astype(int)
    df["plat"] = plat
    return df


def fit_platform(dfs, variant):
    """Fit per-platform coefficients on training data. dfs: list of DataFrames.

    Each variant returns a coef dict. The predict step uses these.
    """
    all_df = pd.concat(dfs, ignore_index=True)
    m = all_df["v_mps"].to_numpy() > 2.0
    yt = all_df["yt"].to_numpy()[m]
    yp = all_df["yaw_rate_pred_rads"].to_numpy()[m]
    v = all_df["v_mps"].to_numpy()[m]
    d = all_df["delta_road_rad"].to_numpy()[m]
    plat = all_df["plat"].iloc[0]

    if variant == "V0":
        return {"variant": "V0"}
    if variant == "V1":
        a = float((yt * yp).sum() / (yp * yp).sum())
        return {"variant": "V1", "a": a}
    if variant == "V2":
        A = np.column_stack([yp, yp ** 3])
        coef, *_ = np.linalg.lstsq(A, yt, rcond=None)
        return {"variant": "V2", "a": float(coef[0]), "b": float(coef[1])}
    if variant == "V3":
        # understeer bicycle: yt = v*delta / (L + Kus * v^2)
        # => v*d / yt = L + Kus*v^2.  Solve for L,Kus by least squares.
        # Filter for non-zero yt
        keep = np.abs(yt) > 0.01
        v_, d_, yt_ = v[keep], d[keep], yt[keep]
        rhs = v_ * d_ / yt_
        A = np.column_stack([np.ones_like(v_), v_ ** 2])
        coef, *_ = np.linalg.lstsq(A, rhs, rcond=None)
        return {"variant": "V3", "L_eff": float(coef[0]), "Kus": float(coef[1])}
    if variant == "V4":
        # yt = a*yp + b*yp*v^2  =>  linear in [yp, yp*v^2]
        A = np.column_stack([yp, yp * v ** 2])
        coef, *_ = np.linalg.lstsq(A, yt, rcond=None)
        return {"variant": "V4", "a": float(coef[0]), "b": float(coef[1])}
    if variant == "V5":
        # yt = a*yp + b*yp**3 + c*yp*v^2
        A = np.column_stack([yp, yp ** 3, yp * v ** 2])
        coef, *_ = np.linalg.lstsq(A, yt, rcond=None)
        return {"variant": "V5", "a": float(coef[0]), "b": float(coef[1]), "c": float(coef[2])}
    raise ValueError(variant)


def apply_variant(sim_df, platform, coefs):
    yp = sim_df["yaw_rate_pred_rads"].to_numpy(float)
    v = sim_df["v_mps"].to_numpy(float)
    d = sim_df["delta_road_rad"].to_numpy(float)
    v0 = coefs["variant"]
    if v0 == "V0":
        return yp
    if v0 == "V1":
        return coefs["a"] * yp
    if v0 == "V2":
        return coefs["a"] * yp + coefs["b"] * yp ** 3
    if v0 == "V3":
        L = coefs["L_eff"]; Kus = coefs["Kus"]
        return v * d / (L + Kus * v ** 2)
    if v0 == "V4":
        return coefs["a"] * yp + coefs["b"] * yp * v ** 2
    if v0 == "V5":
        return coefs["a"] * yp + coefs["b"] * yp ** 3 + coefs["c"] * yp * v ** 2
    raise ValueError(v0)


def score_paths(paths, predict_yp):
    """Score given a function predict_yp(sim_df, platform) -> array of yr."""
    n = nb = 0
    yaw_sum_sq = cte_sum_sq = 0.0
    per_plat = {}
    for p in paths:
        df = load_seg(p)
        if df is None: continue
        plat = df["plat"].iloc[0]
        t = df["t_s"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        if len(t) < 2 or np.any(np.diff(t) <= 0): continue
        yt = df["yt"].to_numpy(float)
        yr = predict_yp(df, plat)
        mask = v > 2.0
        if mask.sum() < 2: continue
        r = (yr[mask] - yt[mask])
        ss = float((r ** 2).sum())
        cte = cte_diagnostics_segment(t, v, yt, yr)
        yaw_sum_sq += ss; n += int(mask.sum())
        cte_sum_sq += cte["sum_sq_m2"]; nb += cte["n_bins"]
        pp = per_plat.setdefault(plat, {"ss": 0., "n": 0, "cs": 0., "nb": 0})
        pp["ss"] += ss; pp["n"] += int(mask.sum())
        pp["cs"] += cte["sum_sq_m2"]; pp["nb"] += cte["n_bins"]
    yaw = math.sqrt(yaw_sum_sq / n) if n else float("nan")
    cte = math.sqrt(cte_sum_sq / nb) if nb else float("nan")
    out = {"yaw_rmse": yaw, "cte_rmse": cte, "n_samples": n, "n_bins": nb, "per_plat": {}}
    for plat, m in per_plat.items():
        out["per_plat"][plat] = {
            "yaw_rmse": math.sqrt(m["ss"] / m["n"]) if m["n"] else float("nan"),
            "cte_rmse": math.sqrt(m["cs"] / m["nb"]) if m["nb"] else float("nan"),
        }
    return out


def main():
    by_plat = load_all()
    # Build train/dev split by route to avoid leakage
    rng = random.Random(0)
    train, dev = {}, {}
    for plat, paths in by_plat.items():
        # route = parents[1].name; group then split routes
        by_route = {}
        for p in paths:
            route = Path(p).resolve().parents[1].name
            by_route.setdefault(route, []).append(p)
        routes = list(by_route.keys()); rng.shuffle(routes)
        n_dev = max(1, len(routes) // 5)
        dev_routes = set(routes[:n_dev])
        tr, dv = [], []
        for route, ps in by_route.items():
            (dv if route in dev_routes else tr).extend(ps)
        train[plat] = tr; dev[plat] = dv
        print(f"{plat}: train n={len(tr)} dev n={len(dv)} (routes train/dev = {len(routes)-n_dev}/{n_dev})")

    variants = ["V0", "V1", "V2", "V3", "V4", "V5"]
    all_dev = [p for ps in dev.values() for p in ps]
    all_train = [p for ps in train.values() for p in ps]

    # Fit per-platform per-variant on training set
    coefs_by_var = {}
    for var in variants:
        coefs_by_var[var] = {}
        for plat, paths in train.items():
            dfs = [load_seg(p) for p in paths]
            dfs = [df for df in dfs if df is not None]
            coefs_by_var[var][plat] = fit_platform(dfs, var)
        print(f"\n== Variant {var} coefficients ==")
        for plat, c in coefs_by_var[var].items():
            print(f"  {plat}: {c}")

    # Evaluate each variant on dev
    print("\n## DEV scores (all platforms pooled)")
    results = {}
    for var in variants:
        def make_pred(coefs_per_plat):
            def predict(df, plat):
                return apply_variant(df, plat, coefs_per_plat[plat])
            return predict
        res = score_paths(all_dev, make_pred(coefs_by_var[var]))
        results[var] = res
        print(f"  {var}: yaw_rmse={res['yaw_rmse']:.6f} cte_rmse={res['cte_rmse']:.4f}")
        for plat, m in res["per_plat"].items():
            print(f"     {plat}: yaw={m['yaw_rmse']:.5f} cte={m['cte_rmse']:.3f}")

    # Save best coefs
    # Pick best per-platform variant based on per-platform CTE (or yaw)
    print("\n## Per-platform best variant (by dev cte_rmse):")
    best = {}
    for plat in by_plat:
        scores = []
        for var in variants:
            r = results[var]["per_plat"].get(plat)
            if r: scores.append((r["cte_rmse"], var))
        scores.sort()
        best_var = scores[0][1] if scores else "V0"
        best[plat] = {"variant": best_var, "coefs": coefs_by_var[best_var][plat]}
        print(f"  {plat}: {best_var}  (dev cte={scores[0][0]:.3f})")

    # Refit best variant per platform on ALL data (train+dev) for final coefs
    final = {}
    for plat in by_plat:
        bv = best[plat]["variant"]
        dfs = [load_seg(p) for p in by_plat[plat]]
        dfs = [df for df in dfs if df is not None]
        final[plat] = fit_platform(dfs, bv)

    print("\n## FINAL coefficients (refit on all data):")
    for plat, c in final.items():
        print(f"  {plat}: {c}")
    (ROOT / "out" / "final_coefs.json").write_text(json.dumps(final, indent=2))
    print("\nSaved out/final_coefs.json")


if __name__ == "__main__":
    main()
