"""V2 exploration:
  - Skip Lightning (at noise floor); ship V1 as-is for Lightning.
  - For Mach-E and IONIQ: try per-segment bias correction at prediction time, computed
    from the V1 vs V0 residual structure (no truth needed). Specifically, look at
    proxy signals: at moments of near-zero steering, the yaw rate prediction should
    be ~0. Any persistent offset is delta0 mis-estimation.
  - Also try a *very low-rank* per-platform global bias only (what bias-only achieves).
  - Also try: linear bias = c0 + c1 * v (so bias scales with speed). Fit per-platform.
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-03")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "code")); sys.path.insert(0, str(ROOT / "_shared"))
from v1_baseline import predict_v1  # type: ignore
from traj_metrics import cte_rmse_segment  # type: ignore

INPUT_COLS = ["t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
              "accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"]
PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5", "FORD_F_150_LIGHTNING_MK1"]

def load_all(platform):
    base = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(base.rglob("sim.csv"))
    segs = []
    for p in paths:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns or len(df) < 50: continue
        for c in INPUT_COLS:
            if c not in df.columns: df[c] = 0.0
        sim_df = df[INPUT_COLS].copy()
        yr_v1 = predict_v1(sim_df, platform)["yaw_rate_pred_rads"].to_numpy()
        segs.append({"path": str(p), "df": df, "sim_df": sim_df, "yr_v1": yr_v1})
    return segs

def yaw_rmse(yr_truth, yr_pred):
    return float(np.sqrt(np.mean((yr_truth - yr_pred) ** 2)))

def cte_pool(segs, get_pred):
    sq = 0.0; n = 0
    for s in segs:
        t = s["df"]["t_s"].to_numpy(); v = s["df"]["v_mps"].to_numpy()
        yr_truth = s["df"]["yaw_rate_meas_rads"].to_numpy()
        yp = get_pred(s)
        sqr, nb, _ = cte_rmse_segment(t, v, yr_truth, yp)
        sq += sqr; n += nb
    return math.sqrt(sq / n) if n else float("nan")

def yaw_pool(segs, get_pred):
    sq = 0.0; n = 0
    for s in segs:
        yr_truth = s["df"]["yaw_rate_meas_rads"].to_numpy()
        yp = get_pred(s)
        sq += float(np.sum((yr_truth - yp) ** 2)); n += len(yr_truth)
    return math.sqrt(sq / n)

def main():
    results = {}
    coeffs = {}
    for plat in PLATFORMS:
        segs = load_all(plat)
        print(f"\n=== {plat} ({len(segs)} segs) ===")
        # Baseline V1
        yaw_v1 = yaw_pool(segs, lambda s: s["yr_v1"])
        cte_v1 = cte_pool(segs, lambda s: s["yr_v1"])
        print(f"V1: yaw={yaw_v1:.6f} cte={cte_v1:.2f}")
        # Global mean residual via 5-fold CV
        rng = np.random.default_rng(42)
        order = np.arange(len(segs)); rng.shuffle(order)
        folds = np.array_split(order, min(5, len(segs)))
        # Global bias only
        biases_global_cv = []
        yp_global = [None]*len(segs)
        for val_idx in folds:
            val_set = set(int(i) for i in val_idx)
            tr_resid = []
            for i, s in enumerate(segs):
                if i in val_set: continue
                tr_resid.append(s["df"]["yaw_rate_meas_rads"].to_numpy() - s["yr_v1"])
            b = float(np.concatenate(tr_resid).mean())
            biases_global_cv.append(b)
            for i in val_set:
                yp_global[i] = segs[i]["yr_v1"] + b
        yaw_g = yaw_pool(segs, lambda s: yp_global[segs.index(s)])
        # the above is O(n^2) — fix:
        idx_by_id = {id(s): i for i, s in enumerate(segs)}
        yaw_g = yaw_pool(segs, lambda s: yp_global[idx_by_id[id(s)]])
        cte_g = cte_pool(segs, lambda s: yp_global[idx_by_id[id(s)]])
        b_final = float(np.mean([s["df"]["yaw_rate_meas_rads"].to_numpy().mean() -
                                  s["yr_v1"].mean() for s in segs]))
        # fit truly global bias (sample-wise mean) on full data
        b_full = float(np.mean(np.concatenate([s["df"]["yaw_rate_meas_rads"].to_numpy() - s["yr_v1"] for s in segs])))
        print(f"V1+gbias(CV): yaw={yaw_g:.6f} ({(yaw_g-yaw_v1)/yaw_v1*100:+.2f}%) "
              f"cte={cte_g:.2f} ({(cte_g-cte_v1)/cte_v1*100:+.2f}%) [b_full={b_full:.6f}]")
        # Linear bias b = c0 + c1 * v: fit per-platform under CV
        yp_lin = [None]*len(segs)
        for val_idx in folds:
            val_set = set(int(i) for i in val_idx)
            Xs, ys = [], []
            for i, s in enumerate(segs):
                if i in val_set: continue
                r = s["df"]["yaw_rate_meas_rads"].to_numpy() - s["yr_v1"]
                v = s["df"]["v_mps"].to_numpy()
                Xs.append(np.column_stack([np.ones_like(v), v])); ys.append(r)
            X = np.vstack(Xs); y = np.concatenate(ys)
            w = np.linalg.lstsq(X, y, rcond=None)[0]
            for i in val_set:
                v = segs[i]["df"]["v_mps"].to_numpy()
                yp_lin[i] = segs[i]["yr_v1"] + w[0] + w[1] * v
        yaw_l = yaw_pool(segs, lambda s: yp_lin[idx_by_id[id(s)]])
        cte_l = cte_pool(segs, lambda s: yp_lin[idx_by_id[id(s)]])
        # fit linear-bias on full data
        Xs, ys = [], []
        for s in segs:
            r = s["df"]["yaw_rate_meas_rads"].to_numpy() - s["yr_v1"]
            v = s["df"]["v_mps"].to_numpy()
            Xs.append(np.column_stack([np.ones_like(v), v])); ys.append(r)
        X = np.vstack(Xs); y = np.concatenate(ys)
        w_full = np.linalg.lstsq(X, y, rcond=None)[0]
        print(f"V1+linbias(CV): yaw={yaw_l:.6f} ({(yaw_l-yaw_v1)/yaw_v1*100:+.2f}%) "
              f"cte={cte_l:.2f} ({(cte_l-cte_v1)/cte_v1*100:+.2f}%) [w={w_full.tolist()}]")
        # Scale-only: yr_post = scale * yr_v1; fit scale.
        yp_sc = [None]*len(segs)
        for val_idx in folds:
            val_set = set(int(i) for i in val_idx)
            num = 0.0; den = 0.0
            for i, s in enumerate(segs):
                if i in val_set: continue
                yt = s["df"]["yaw_rate_meas_rads"].to_numpy()
                yv = s["yr_v1"]
                num += float(np.sum(yt * yv)); den += float(np.sum(yv * yv))
            sc = num / den if den else 1.0
            for i in val_set:
                yp_sc[i] = sc * segs[i]["yr_v1"]
        yaw_s = yaw_pool(segs, lambda s: yp_sc[idx_by_id[id(s)]])
        cte_s = cte_pool(segs, lambda s: yp_sc[idx_by_id[id(s)]])
        num = 0.0; den = 0.0
        for s in segs:
            yt = s["df"]["yaw_rate_meas_rads"].to_numpy(); yv = s["yr_v1"]
            num += float(np.sum(yt * yv)); den += float(np.sum(yv * yv))
        sc_full = num/den
        print(f"V1+scale(CV): yaw={yaw_s:.6f} ({(yaw_s-yaw_v1)/yaw_v1*100:+.2f}%) "
              f"cte={cte_s:.2f} ({(cte_s-cte_v1)/cte_v1*100:+.2f}%) [scale={sc_full:.5f}]")
        # Scale + bias: yr_post = a + b*yr_v1, fit (a,b) jointly
        yp_ab = [None]*len(segs)
        for val_idx in folds:
            val_set = set(int(i) for i in val_idx)
            Xs, ys = [], []
            for i, s in enumerate(segs):
                if i in val_set: continue
                yt = s["df"]["yaw_rate_meas_rads"].to_numpy(); yv = s["yr_v1"]
                Xs.append(np.column_stack([np.ones_like(yv), yv])); ys.append(yt)
            X = np.vstack(Xs); y = np.concatenate(ys)
            w = np.linalg.lstsq(X, y, rcond=None)[0]
            for i in val_set:
                yp_ab[i] = w[0] + w[1] * segs[i]["yr_v1"]
        yaw_ab = yaw_pool(segs, lambda s: yp_ab[idx_by_id[id(s)]])
        cte_ab = cte_pool(segs, lambda s: yp_ab[idx_by_id[id(s)]])
        Xs, ys = [], []
        for s in segs:
            yt = s["df"]["yaw_rate_meas_rads"].to_numpy(); yv = s["yr_v1"]
            Xs.append(np.column_stack([np.ones_like(yv), yv])); ys.append(yt)
        X = np.vstack(Xs); y = np.concatenate(ys)
        w_ab = np.linalg.lstsq(X, y, rcond=None)[0]
        print(f"V1+scale+bias(CV): yaw={yaw_ab:.6f} ({(yaw_ab-yaw_v1)/yaw_v1*100:+.2f}%) "
              f"cte={cte_ab:.2f} ({(cte_ab-cte_v1)/cte_v1*100:+.2f}%) [a={w_ab[0]:.6f} b={w_ab[1]:.5f}]")

        results[plat] = {
            "v1": {"yaw": yaw_v1, "cte": cte_v1},
            "gbias": {"yaw": yaw_g, "cte": cte_g, "b": b_full},
            "linbias": {"yaw": yaw_l, "cte": cte_l, "w": w_full.tolist()},
            "scale": {"yaw": yaw_s, "cte": cte_s, "scale": sc_full},
            "scale_bias": {"yaw": yaw_ab, "cte": cte_ab, "a": float(w_ab[0]), "b": float(w_ab[1])},
        }
        coeffs[plat] = {
            "gbias_b": b_full,
            "linbias_w": w_full.tolist(),
            "scale": sc_full,
            "scale_bias": [float(w_ab[0]), float(w_ab[1])],
        }
    (ROOT / "out" / "v2_results.json").write_text(json.dumps(results, indent=2))
    (ROOT / "out" / "v2_coeffs.json").write_text(json.dumps(coeffs, indent=2))

if __name__ == "__main__":
    main()
