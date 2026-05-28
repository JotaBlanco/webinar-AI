"""Shapley-style attribution: average marginal MSE-drop contribution of each
variant over all orderings.

Variants:
  V1 — global yaw-rate bias subtraction
  V2 — refit steering ratio scalar k
  V3 — time-align steering relative to yaw (per-segment lag, global median used)
  V4 — linear understeer correction
"""
from __future__ import annotations
import glob, os, json, itertools
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-09/data/sim/segments"
PLATS = {
    "FORD_F_150_LIGHTNING_MK1": {"L": 3.70, "i_s": 16.9},
    "FORD_MUSTANG_MACH_E_MK1":  {"L": 2.984, "i_s": 17.0},
}
V_MIN = 2.0

def load_all():
    out = {}
    for plat in PLATS:
        frames = []
        for csv in sorted(glob.glob(os.path.join(ROOT, plat, "*", "*", "*", "sim.csv"))):
            try:
                df = pd.read_csv(csv, usecols=[
                    "v_mps","delta_road_rad","yaw_rate_meas_rads",
                ])
            except Exception: continue
            df["seg"] = csv
            frames.append(df)
        out[plat] = frames
    return out

def predict_ks(v, d, L): return (v / L) * np.tan(d)

def apply_lag(arr, k):
    if k == 0: return arr.copy()
    if k > 0:  return np.concatenate([arr[k:], np.full(k, arr[-1])])
    kk = -k;   return np.concatenate([np.full(kk, arr[0]), arr[:-kk]])

def find_best_lag_global(segments, L, max_lag=20):
    """Median of per-segment best lag."""
    lags = []
    for df in segments:
        mm = df["v_mps"].values > V_MIN
        if mm.sum() < 200: continue
        vv = df["v_mps"].values[mm]
        dd = df["delta_road_rad"].values[mm]
        yy = df["yaw_rate_meas_rads"].values[mm]
        if np.std(dd) < 1e-4: continue
        best, br = 0, None
        for k in range(-max_lag, max_lag+1):
            d_sh = apply_lag(dd, k)
            r = float(np.mean((predict_ks(vv, d_sh, L) - yy)**2))
            if br is None or r < br: br, best = r, k
        lags.append(best)
    return int(np.median(lags)) if lags else 0

def fit_k_ratio(v, d, L, y):
    x = (v / L) * d
    return float(np.sum(x*y)/np.sum(x*x))

def fit_us(v, d, L, y):
    p0 = predict_ks(v, d, L)
    rhs = p0 - y
    x = v*v*y
    return float(np.sum(x*rhs)/np.sum(x*x))

def evaluate(segments, L, subset, fit_params):
    """Given a subset of variants (e.g. {'V2','V4'}), compute pooled MSE."""
    sse, n = 0.0, 0
    lag = fit_params["lag"] if "V3" in subset else 0
    k_ratio = fit_params["k_ratio"] if "V2" in subset else 1.0
    K_us = fit_params["K_us"] if "V4" in subset else 0.0
    bias = fit_params["bias"] if "V1" in subset else 0.0
    for df in segments:
        mm = df["v_mps"].values > V_MIN
        if mm.sum() < 10: continue
        vv = df["v_mps"].values[mm]
        dd = df["delta_road_rad"].values[mm]
        yy = df["yaw_rate_meas_rads"].values[mm]
        d_sh = apply_lag(dd, lag)
        p = predict_ks(vv, k_ratio * d_sh, L)
        if K_us != 0.0:
            p = p / (1.0 + K_us * vv * vv)
        p = p - bias
        sse += float(np.sum((p - yy)**2))
        n += len(vv)
    return sse / n

def fit_all_jointly(segments, L, subset_for_fit):
    """Fit (lag, k_ratio, K_us, bias) using only variants in subset_for_fit.
    We do the standard 'do lag first then fit downstream' for stability.
    """
    lag = find_best_lag_global(segments, L) if "V3" in subset_for_fit else 0
    # build pooled arrays after lag
    vs, ds, ys = [], [], []
    for df in segments:
        mm = df["v_mps"].values > V_MIN
        if mm.sum() < 10: continue
        vv = df["v_mps"].values[mm]
        dd = df["delta_road_rad"].values[mm]
        yy = df["yaw_rate_meas_rads"].values[mm]
        d_sh = apply_lag(dd, lag)
        vs.append(vv); ds.append(d_sh); ys.append(yy)
    v = np.concatenate(vs); d = np.concatenate(ds); y = np.concatenate(ys)
    k_ratio = fit_k_ratio(v, d, L, y) if "V2" in subset_for_fit else 1.0
    # understeer fit on after k_ratio scaling
    K_us = fit_us(v, k_ratio * d, L, y) if "V4" in subset_for_fit else 0.0
    # bias = residual mean of current model
    p = predict_ks(v, k_ratio*d, L)
    if K_us != 0.0: p = p / (1.0 + K_us * v * v)
    bias = float(np.mean(p - y)) if "V1" in subset_for_fit else 0.0
    return {"lag": lag, "k_ratio": k_ratio, "K_us": K_us, "bias": bias}

def shapley(segments, L):
    variants = ["V1", "V2", "V3", "V4"]
    # cache MSE for every subset using best-fit params for that subset
    cache = {}
    for r in range(0, len(variants)+1):
        for combo in itertools.combinations(variants, r):
            s = frozenset(combo)
            fits = fit_all_jointly(segments, L, s)
            cache[s] = evaluate(segments, L, s, fits)
    base_mse = cache[frozenset()]
    full_mse = cache[frozenset(variants)]
    shap = {v: 0.0 for v in variants}
    import math
    n = len(variants)
    for v in variants:
        for combo in itertools.chain.from_iterable(
            itertools.combinations([x for x in variants if x != v], r)
            for r in range(0, n)
        ):
            S = frozenset(combo)
            S_v = frozenset(combo + (v,))
            weight = math.factorial(len(S)) * math.factorial(n - len(S) - 1) / math.factorial(n)
            # MSE-drop = MSE(S) - MSE(S+v)
            shap[v] += weight * (cache[S] - cache[S_v])
    return {
        "base_mse": base_mse,
        "full_mse": full_mse,
        "base_rmse": float(np.sqrt(base_mse)),
        "full_rmse": float(np.sqrt(full_mse)),
        "shapley_mse_drop": shap,
        "shapley_pct_of_total_drop": {v: 100*shap[v]/(base_mse-full_mse) if (base_mse-full_mse)>0 else 0.0 for v in variants},
        "fits_full": fit_all_jointly(segments, L, frozenset(variants)),
    }

if __name__ == "__main__":
    data = load_all()
    out = {}
    for plat, segs in data.items():
        print(f"\n=== {plat} ===")
        L = PLATS[plat]["L"]
        r = shapley(segs, L)
        out[plat] = r
        print(json.dumps(r, indent=2))
    # pool
    pool = {}
    pool["pooled_base_rmse"] = float(np.sqrt(
        sum(out[p]["base_mse"] * sum(len(df) for df in data[p]) for p in out) /
        sum(sum(len(df) for df in data[p]) for p in out)
    ))
    pool["pooled_full_rmse"] = float(np.sqrt(
        sum(out[p]["full_mse"] * sum(len(df) for df in data[p]) for p in out) /
        sum(sum(len(df) for df in data[p]) for p in out)
    ))
    pool["pct_rmse_reduction"] = 100*(1 - pool["pooled_full_rmse"]/pool["pooled_base_rmse"])
    print("\n=== POOLED ===")
    print(json.dumps(pool, indent=2))
    with open("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-09/out/shapley.json","w") as f:
        json.dump({"per_platform": out, "pooled": pool}, f, indent=2)
