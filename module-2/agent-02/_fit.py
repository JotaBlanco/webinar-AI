"""Fit per-platform corrections to improve yaw-rate prediction.

Model variants:
  V0:  psi_dot = (v/L) * tan(delta)    [pre-computed baseline]
  V1:  psi_dot = (v/L) * tan(delta)  -- but with effective L per platform (fit)
  V2:  psi_dot = v * delta / (L + K_us * v^2)    [linear-tire understeer]
  V3:  V2 + steering bias/scale: delta_eff = a*delta + b
  V4:  V3 + lag (first-order steering dynamics, fit tau per platform)

We fit on a train split and evaluate on a held-out dev split.
"""
import sys
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "skills" / "score-model"))
sys.path.insert(0, str(HERE / "_shared"))
from score import score
from traj_metrics import cte_rmse_segment

DATA_ROOT = HERE / "data" / "sim" / "segments"
PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]
L_BY = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}


def list_segments(platform):
    root = DATA_ROOT / platform
    return sorted(root.glob("**/sim.csv"))


def load_segment(p):
    df = pd.read_csv(p)
    return df


def split_train_dev(paths, frac=0.7, seed=42):
    rng = np.random.default_rng(seed)
    idx = np.arange(len(paths))
    rng.shuffle(idx)
    cut = int(len(paths) * frac)
    return [paths[i] for i in idx[:cut]], [paths[i] for i in idx[cut:]]


def gather_arrays(paths, v_min=2.0):
    """Concatenate (delta, v, yr_meas) across segments — sample-pooled."""
    delta_list = []
    v_list = []
    yr_list = []
    for p in paths:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        mask = df["v_mps"].to_numpy() > v_min
        delta_list.append(df["delta_road_rad"].to_numpy()[mask])
        v_list.append(df["v_mps"].to_numpy()[mask])
        yr_list.append(df["yaw_rate_meas_rads"].to_numpy()[mask])
    return (np.concatenate(delta_list), np.concatenate(v_list), np.concatenate(yr_list))


def predict_v2(delta, v, L, K_us):
    """Linear-tire understeer (bicycle, steady-state)."""
    return v * delta / (L + K_us * v * v)


def predict_v3(delta, v, L, K_us, a_scale, b_off):
    delta_eff = a_scale * delta + b_off
    return v * delta_eff / (L + K_us * v * v)


def fit_v2(delta, v, yr, L0):
    """Fit K_us only, L fixed to nominal."""
    def loss(params):
        (K_us,) = params
        pred = predict_v2(delta, v, L0, K_us)
        return np.mean((pred - yr) ** 2)
    res = minimize(loss, [0.0], method="Nelder-Mead", options={"xatol": 1e-6, "fatol": 1e-10})
    return res.x[0]


def fit_v3(delta, v, yr, L0):
    def loss(params):
        K_us, a, b = params
        pred = predict_v3(delta, v, L0, K_us, a, b)
        return np.mean((pred - yr) ** 2)
    res = minimize(loss, [0.0, 1.0, 0.0], method="Nelder-Mead",
                   options={"xatol": 1e-7, "fatol": 1e-12, "maxiter": 5000})
    return res.x


def fit_v4_with_L(delta, v, yr):
    """Fit K_us, L_eff, a_scale, b_off jointly."""
    def loss(params):
        L_eff, K_us, a, b = params
        if L_eff <= 0.5 or L_eff > 6.0:
            return 1e9
        pred = predict_v3(delta, v, L_eff, K_us, a, b)
        return np.mean((pred - yr) ** 2)
    res = minimize(loss, [3.0, 0.0, 1.0, 0.0], method="Nelder-Mead",
                   options={"xatol": 1e-7, "fatol": 1e-12, "maxiter": 10000})
    return res.x


def main():
    all_results = {}
    coeffs = {}
    for platform in PLATFORMS:
        paths = list_segments(platform)
        train, dev = split_train_dev(paths)
        print(f"\n=== {platform} ===")
        print(f"  segments: {len(paths)} (train={len(train)}, dev={len(dev)})")
        L0 = L_BY[platform]
        delta_tr, v_tr, yr_tr = gather_arrays(train)
        delta_dv, v_dv, yr_dv = gather_arrays(dev)
        print(f"  train samples: {len(delta_tr)},  dev samples: {len(delta_dv)}")

        # V0 baseline (use precomputed)
        def v0_rmse(paths_):
            sse = 0.0; n = 0
            for p in paths_:
                df = pd.read_csv(p)
                m = df["v_mps"].to_numpy() > 2.0
                r = df["yaw_rate_pred_rads"].to_numpy()[m] - df["yaw_rate_meas_rads"].to_numpy()[m]
                sse += float(np.sum(r*r)); n += int(m.sum())
            return (sse/n)**0.5 if n else float("nan")
        v0_dev = v0_rmse(dev)

        # V2 fit
        K_us = fit_v2(delta_tr, v_tr, yr_tr, L0)
        pred = predict_v2(delta_dv, v_dv, L0, K_us)
        v2_dev = float(np.sqrt(np.mean((pred - yr_dv) ** 2)))

        # V3 fit
        K_us3, a3, b3 = fit_v3(delta_tr, v_tr, yr_tr, L0)
        pred = predict_v3(delta_dv, v_dv, L0, K_us3, a3, b3)
        v3_dev = float(np.sqrt(np.mean((pred - yr_dv) ** 2)))

        # V4 fit (free L)
        L4, K_us4, a4, b4 = fit_v4_with_L(delta_tr, v_tr, yr_tr)
        pred = predict_v3(delta_dv, v_dv, L4, K_us4, a4, b4)
        v4_dev = float(np.sqrt(np.mean((pred - yr_dv) ** 2)))

        print(f"  V0 dev yaw-rate RMSE   : {v0_dev:.6f}")
        print(f"  V2 (K_us only)         : {v2_dev:.6f}   K_us={K_us:.4g}")
        print(f"  V3 (K_us+scale+bias)   : {v3_dev:.6f}   K_us={K_us3:.4g} a={a3:.4f} b={b3:.4g}")
        print(f"  V4 (+L free)           : {v4_dev:.6f}   L={L4:.4f} K_us={K_us4:.4g} a={a4:.4f} b={b4:.4g}")

        all_results[platform] = dict(v0=v0_dev, v2=v2_dev, v3=v3_dev, v4=v4_dev)
        coeffs[platform] = dict(
            L_nominal=L0,
            v2=dict(K_us=float(K_us), L=L0),
            v3=dict(K_us=float(K_us3), a_scale=float(a3), b_off=float(b3), L=L0),
            v4=dict(L=float(L4), K_us=float(K_us4), a_scale=float(a4), b_off=float(b4)),
        )

    with open(HERE / "_fit_results.json", "w") as f:
        json.dump({"results": all_results, "coeffs": coeffs}, f, indent=2)
    print("\nWrote _fit_results.json")


if __name__ == "__main__":
    main()
