"""V2 longitudinal model:

    a_pred = c_throttle * pedal + c_brake0 * brake - c_drag * v^2 - c_roll * v + bias

Per-platform fit using non-negative constraints on drag/roll to keep things
physical, then re-evaluate open-loop and closed-loop.
"""
import os, json
import numpy as np
import pandas as pd
from scipy.optimize import nnls

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-03"
OUT = f"{ROOT}/out"

df = pd.read_parquet(f"{OUT}/long_dataset.parquet")
PLATFORMS = sorted(df["platform"].unique())

# segment-level split
rng = np.random.default_rng(42)
seg_ids = df["seg_id"].unique()
rng.shuffle(seg_ids)
n_test = max(1, int(0.25 * len(seg_ids)))
test_segs = set(seg_ids[:n_test])
train_segs = set(seg_ids[n_test:])
train = df[df["seg_id"].isin(train_segs)].copy()
test  = df[df["seg_id"].isin(test_segs)].copy()


# Solve constrained LS:
#   a = c_t * pedal + c_b * brake - c_d * v^2 - c_r * v + bias
# Let coeffs = [c_t, c_b, c_d, c_r, bias] with c_d, c_r >= 0
# Rewrite as nonneg LS by separating signs: with substitution use scipy.optimize.minimize?
# Simpler: solve unconstrained linear LS, then if c_d<0 or c_r<0, set to 0 and refit.

def fit_platform(sub):
    v = sub["v_mps"].values
    pe = sub["accel_pedal_pct"].values
    b = sub["brake"].values
    y = sub["a_long_mps2"].values
    # design: [pedal, brake, -v^2, -v, 1] so coefficients are [c_t, c_b, c_d, c_r, bias]
    X = np.column_stack([pe, b, -v*v, -v, np.ones_like(v)])
    # First unconstrained solve
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    c_t, c_b, c_d, c_r, bias = coef
    # Enforce non-negativity on drag and roll
    fixed_drag = c_d < 0
    fixed_roll = c_r < 0
    if fixed_drag or fixed_roll:
        cols = []
        idxs = []
        if not fixed_drag: cols.append(-v*v); idxs.append("c_d")
        if not fixed_roll: cols.append(-v);   idxs.append("c_r")
        Xn = np.column_stack([pe, b] + cols + [np.ones_like(v)])
        coefn, *_ = np.linalg.lstsq(Xn, y, rcond=None)
        c_t = coefn[0]; c_b = coefn[1]
        i = 2
        c_d2 = 0.0 if fixed_drag else coefn[i]; i += 0 if fixed_drag else 1
        c_r2 = 0.0 if fixed_roll else coefn[i]; i += 0 if fixed_roll else 1
        bias = coefn[-1]
        c_d, c_r = c_d2, c_r2
    return {"c_throttle": float(c_t), "c_brake0": float(c_b),
            "c_drag": float(c_d), "c_roll": float(c_r), "bias": float(bias)}


params = {}
for plat in PLATFORMS:
    sub = train[train["platform"] == plat]
    params[plat] = fit_platform(sub)
    print(f"{plat}: {params[plat]}")

with open(f"{OUT}/params_v2.json", "w") as f:
    json.dump(params, f, indent=2)


def predict_a(d, plat):
    p = params[plat]
    v = d["v_mps"].values
    pe = d["accel_pedal_pct"].values
    b = d["brake"].values
    return (p["c_throttle"] * pe + p["c_brake0"] * b
            - p["c_drag"] * v * v - p["c_roll"] * v + p["bias"])


# --- open-loop metrics (a_long, v_mps next-step) ---
def open_loop(d, label):
    rows = []
    for plat in PLATFORMS:
        sub = d[d["platform"] == plat]
        if not len(sub):
            continue
        a_pred = predict_a(sub, plat)
        a_true = sub["a_long_mps2"].values
        rows.append({
            "platform": plat, "n": len(sub),
            "a_mae": float(np.mean(np.abs(a_pred - a_true))),
            "a_rmse": float(np.sqrt(np.mean((a_pred-a_true)**2))),
            "a_baseline_mae": float(np.mean(np.abs(a_true))),
        })
    out = pd.DataFrame(rows)
    print(f"\n=== Open-loop (one-step a) {label} ===")
    print(out.to_string(index=False))
    return out

open_loop(train, "train")
ol = open_loop(test, "test")
ol.to_csv(f"{OUT}/ol_v2_test.csv", index=False)


# --- closed-loop integration (predict v over horizon) ---
HORIZON_S = 30.0

def closed_loop(d, label):
    per = []
    for plat in PLATFORMS:
        for seg_id, g in d[d["platform"]==plat].groupby("seg_id"):
            g = g.reset_index(drop=True)
            t0 = g["t_s"].iloc[0]
            g = g[g["t_s"] - t0 <= HORIZON_S].reset_index(drop=True)
            if len(g) < 10: continue
            dt = np.diff(g["t_s"].values, prepend=g["t_s"].values[0])
            dt[0] = dt[1] if len(dt) > 1 else 0.02
            v_meas = g["v_mps"].values
            pe = g["accel_pedal_pct"].values
            br = g["brake"].values
            v_sim = np.zeros_like(v_meas)
            v_sim[0] = v_meas[0]
            p = params[plat]
            A_MIN, A_MAX = -10.0, 6.0  # m/s^2 physical bounds
            for k in range(len(g)-1):
                vk = min(80.0, max(0.0, v_sim[k]))  # clamp v for numerics
                a = (p["c_throttle"]*pe[k] + p["c_brake0"]*br[k]
                     - p["c_drag"]*vk*vk - p["c_roll"]*vk + p["bias"])
                a = np.clip(a, A_MIN, A_MAX)
                v_sim[k+1] = max(0.0, v_sim[k] + a*dt[k+1])
            v_base = np.full_like(v_meas, v_meas[0])
            per.append({
                "platform": plat, "seg_id": seg_id, "n": len(g),
                "v_mae_model": float(np.mean(np.abs(v_sim - v_meas))),
                "v_rmse_model": float(np.sqrt(np.mean((v_sim - v_meas)**2))),
                "v_mae_base": float(np.mean(np.abs(v_base - v_meas))),
                "v_range_mps": float(v_meas.max() - v_meas.min()),
            })
    per_df = pd.DataFrame(per)
    agg = per_df.groupby("platform").agg(
        n_seg=("seg_id","count"),
        v_mae_model=("v_mae_model","mean"),
        v_rmse_model=("v_rmse_model","mean"),
        v_mae_base=("v_mae_base","mean"),
        v_range_mean=("v_range_mps","mean"),
    ).reset_index()
    print(f"\n=== Closed-loop {HORIZON_S:.0f}s on {label} ===")
    print(agg.to_string(index=False))
    return per_df, agg

cl_per, cl_agg = closed_loop(test, "test")
cl_per.to_csv(f"{OUT}/cl_v2_per_test.csv", index=False)
cl_agg.to_csv(f"{OUT}/cl_v2_agg_test.csv", index=False)


# --- regime breakdown using a_long sign / pedal / brake ---
# accel: pedal > 10 & a > 0.3
# brake: brake==1 or a < -0.5
# cruise: |a| < 0.3 & v > 5
# coast: pedal < 2 & brake==0 & v > 2 & a < 0
# stopped: v < 1
def label_regime_vec(d):
    v = d["v_mps"].values
    a = d["a_long_mps2"].values
    pe = d["accel_pedal_pct"].values
    br = d["brake"].values
    lab = np.full(len(d), "other", dtype=object)
    lab[(v < 1.0)] = "stopped"
    lab[(v >= 1.0) & (pe < 2) & (br == 0) & (a < -0.1)] = "coast"
    lab[(v >= 5.0) & (np.abs(a) < 0.3) & (pe >= 2) & (br == 0)] = "cruise"
    lab[(pe > 10) & (a > 0.3)] = "accel"
    lab[(br == 1) | ((a < -0.8) & (pe < 5))] = "brake"
    return lab

def regime_breakdown(d, label):
    d = d.copy()
    d["regime"] = label_regime_vec(d)
    rows = []
    for (plat, reg), g in d.groupby(["platform","regime"]):
        a_pred = predict_a(g, plat)
        err = a_pred - g["a_long_mps2"].values
        rows.append({"platform": plat, "regime": reg, "n": len(g),
                     "a_mae": float(np.mean(np.abs(err))),
                     "a_rmse": float(np.sqrt(np.mean(err**2))),
                     "baseline_mae": float(np.mean(np.abs(g["a_long_mps2"])))})
    out = pd.DataFrame(rows).sort_values(["platform","regime"])
    print(f"\n=== Regime breakdown {label} ===")
    print(out.to_string(index=False))
    return out

reg = regime_breakdown(test, "test (full)")
reg.to_csv(f"{OUT}/regime_v2_test.csv", index=False)


# Overall headline: mean v MAE across test segments (closed-loop)
headline_model = float(cl_per["v_mae_model"].mean())
headline_base  = float(cl_per["v_mae_base"].mean())
print(f"\nHEADLINE (closed-loop {HORIZON_S:.0f}s v MAE):")
print(f"  baseline (hold v0): {headline_base:.3f} m/s")
print(f"  v2 model:          {headline_model:.3f} m/s")
print(f"  improvement:       {(1 - headline_model/headline_base)*100:.1f}%")

with open(f"{OUT}/summary_v2.json", "w") as f:
    json.dump({
        "params": params,
        "horizon_s": HORIZON_S,
        "headline_v_mae_base": headline_base,
        "headline_v_mae_model": headline_model,
        "open_loop_test": ol.to_dict("records"),
        "closed_loop_agg_test": cl_agg.to_dict("records"),
        "regime_test": reg.to_dict("records"),
    }, f, indent=2)
print(f"\nSaved {OUT}/summary_v2.json")
