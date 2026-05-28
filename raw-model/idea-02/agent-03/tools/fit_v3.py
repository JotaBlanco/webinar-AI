"""V3 fit: trim outliers, add IMU-baseline closed-loop, fairer reporting.

Two models compared, plus two baselines:
  - BASELINE_HOLD:   v_pred(t) = v_meas(0)           (no model)
  - BASELINE_IMU:    integrate measured a_long       (uses sensed a, not commanded)
  - MODEL_LINEAR:    a_pred = c_t*pedal + c_b*brake - c_d*v^2 - c_r*v + bias
                     integrated forward; uses ONLY commanded inputs (pedal, brake)

Trim |a_long| > 8 m/s^2 as bad data. Train/test split by segment.
"""
import os, json
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-03"
OUT = f"{ROOT}/out"

df = pd.read_parquet(f"{OUT}/long_dataset.parquet")
PLATFORMS = sorted(df["platform"].unique())

# --- clean ---
A_PHYS_MAX = 8.0  # m/s^2 plausible vehicle bound
n_before = len(df)
df = df[df["a_long_mps2"].abs() <= A_PHYS_MAX].copy()
print(f"Dropped {n_before - len(df):,} rows with |a_long|>{A_PHYS_MAX}")

# --- split ---
rng = np.random.default_rng(42)
seg_ids = df["seg_id"].unique()
rng.shuffle(seg_ids)
n_test = max(1, int(0.25 * len(seg_ids)))
test_segs = set(seg_ids[:n_test])
train_segs = set(seg_ids[n_test:])
train = df[df["seg_id"].isin(train_segs)].copy()
test  = df[df["seg_id"].isin(test_segs)].copy()
print(f"Train segs={len(train_segs)} ({len(train):,} rows)  Test segs={len(test_segs)} ({len(test):,} rows)")


def fit_platform(sub):
    v = sub["v_mps"].values
    pe = sub["accel_pedal_pct"].values
    b = sub["brake"].values
    y = sub["a_long_mps2"].values
    # Design: [pedal, brake, -v^2, -v, 1]
    X = np.column_stack([pe, b, -v*v, -v, np.ones_like(v)])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    c_t, c_b, c_d, c_r, bias = coef
    # Force drag and roll non-negative: refit dropping negative ones
    drop_d = c_d < 0
    drop_r = c_r < 0
    if drop_d or drop_r:
        cols = [pe, b]
        names = ["c_t", "c_b"]
        if not drop_d: cols.append(-v*v); names.append("c_d")
        if not drop_r: cols.append(-v);   names.append("c_r")
        cols.append(np.ones_like(v));     names.append("bias")
        Xn = np.column_stack(cols)
        coefn, *_ = np.linalg.lstsq(Xn, y, rcond=None)
        out = dict(zip(names, coefn))
        c_t = out["c_t"]; c_b = out["c_b"]
        c_d = out.get("c_d", 0.0)
        c_r = out.get("c_r", 0.0)
        bias = out["bias"]
    return dict(c_throttle=float(c_t), c_brake0=float(c_b),
                c_drag=float(c_d), c_roll=float(c_r), bias=float(bias))


params = {plat: fit_platform(train[train["platform"]==plat]) for plat in PLATFORMS}
for p, v in params.items(): print(f"{p}: {v}")

with open(f"{OUT}/params_v3.json","w") as f: json.dump(params, f, indent=2)


def predict_a(d, plat):
    p = params[plat]
    v = d["v_mps"].values; pe = d["accel_pedal_pct"].values; b = d["brake"].values
    return (p["c_throttle"]*pe + p["c_brake0"]*b
            - p["c_drag"]*v*v - p["c_roll"]*v + p["bias"])


# --- open-loop ---
rows = []
for plat in PLATFORMS:
    sub = test[test["platform"]==plat]
    a_pred = predict_a(sub, plat); a_true = sub["a_long_mps2"].values
    rows.append({"platform": plat, "n": len(sub),
                 "a_mae": float(np.mean(np.abs(a_pred - a_true))),
                 "a_rmse": float(np.sqrt(np.mean((a_pred - a_true)**2))),
                 "a_baseline_zero_mae": float(np.mean(np.abs(a_true)))})
ol = pd.DataFrame(rows); print("\n=== Open-loop a (test) ===\n", ol.to_string(index=False))


HORIZON_S = 30.0
A_CLIP = (-8.0, 6.0)
V_CLIP = (0.0, 80.0)

def closed_loop_eval(d):
    out = []
    for plat in PLATFORMS:
        for seg_id, g in d[d["platform"]==plat].groupby("seg_id"):
            g = g.reset_index(drop=True)
            g = g[g["t_s"] - g["t_s"].iloc[0] <= HORIZON_S].reset_index(drop=True)
            if len(g) < 10: continue
            t = g["t_s"].values
            dt = np.diff(t, prepend=t[0]); dt[0] = dt[1] if len(dt)>1 else 0.02
            v_meas = g["v_mps"].values
            pe = g["accel_pedal_pct"].values; br = g["brake"].values
            a_meas = g["a_long_mps2"].values
            p = params[plat]

            # MODEL
            v_sim = np.empty_like(v_meas); v_sim[0] = v_meas[0]
            for k in range(len(g)-1):
                vk = np.clip(v_sim[k], *V_CLIP)
                a = (p["c_throttle"]*pe[k] + p["c_brake0"]*br[k]
                     - p["c_drag"]*vk*vk - p["c_roll"]*vk + p["bias"])
                a = float(np.clip(a, *A_CLIP))
                v_sim[k+1] = max(0.0, v_sim[k] + a * dt[k+1])

            # IMU baseline (integrate measured a_long)
            v_imu = np.empty_like(v_meas); v_imu[0] = v_meas[0]
            for k in range(len(g)-1):
                v_imu[k+1] = max(0.0, v_imu[k] + a_meas[k] * dt[k+1])

            v_hold = np.full_like(v_meas, v_meas[0])

            out.append({
                "platform": plat, "seg_id": seg_id, "n": len(g),
                "v_range": float(v_meas.max() - v_meas.min()),
                "v_mean": float(v_meas.mean()),
                "mae_model": float(np.mean(np.abs(v_sim - v_meas))),
                "mae_imu":   float(np.mean(np.abs(v_imu - v_meas))),
                "mae_hold":  float(np.mean(np.abs(v_hold - v_meas))),
                "rmse_model": float(np.sqrt(np.mean((v_sim - v_meas)**2))),
                "rmse_imu":   float(np.sqrt(np.mean((v_imu - v_meas)**2))),
                "rmse_hold":  float(np.sqrt(np.mean((v_hold - v_meas)**2))),
            })
    return pd.DataFrame(out)

cl = closed_loop_eval(test)
agg = cl.groupby("platform").agg(
    n_seg=("seg_id","count"),
    v_range_mean=("v_range","mean"),
    mae_model=("mae_model","mean"),
    mae_imu=("mae_imu","mean"),
    mae_hold=("mae_hold","mean"),
    rmse_model=("rmse_model","mean"),
).reset_index()
print(f"\n=== Closed-loop {HORIZON_S:.0f}s (test) ===\n", agg.to_string(index=False))
cl.to_csv(f"{OUT}/cl_v3_per_test.csv", index=False)
agg.to_csv(f"{OUT}/cl_v3_agg_test.csv", index=False)


# regime breakdown using vectorised labels on test
def labels(d):
    v = d["v_mps"].values; a = d["a_long_mps2"].values
    pe = d["accel_pedal_pct"].values; br = d["brake"].values
    lab = np.full(len(d), "transition", dtype=object)
    lab[v < 1.0] = "stopped"
    cruise_mask = (v >= 5.0) & (np.abs(a) < 0.3) & (br == 0)
    lab[cruise_mask] = "cruise"
    coast_mask = (v >= 1.0) & (pe < 2) & (br == 0) & (a < -0.05)
    lab[coast_mask] = "coast"
    accel_mask = (pe > 15) & (a > 0.3) & (br == 0)
    lab[accel_mask] = "accel"
    brake_mask = (br == 1) | (a < -1.0)
    lab[brake_mask] = "brake"
    return lab

test2 = test.copy(); test2["regime"] = labels(test2)
rrows = []
for (plat, reg), g in test2.groupby(["platform","regime"]):
    a_pred = predict_a(g, plat)
    err = a_pred - g["a_long_mps2"].values
    rrows.append({"platform": plat, "regime": reg, "n": len(g),
                  "a_mae": float(np.mean(np.abs(err))),
                  "baseline_zero_mae": float(np.mean(np.abs(g["a_long_mps2"])))})
reg_df = pd.DataFrame(rrows).sort_values(["platform","regime"])
print(f"\n=== Regime breakdown (open-loop a) test ===\n", reg_df.to_string(index=False))
reg_df.to_csv(f"{OUT}/regime_v3_test.csv", index=False)


# overall headline
headline_model = float(cl["mae_model"].mean())
headline_hold  = float(cl["mae_hold"].mean())
headline_imu   = float(cl["mae_imu"].mean())
print(f"\n=== Headline (closed-loop {HORIZON_S:.0f}s v MAE, mean across test segments) ===")
print(f"  hold-v0 baseline:   {headline_hold:.3f} m/s")
print(f"  IMU-integrated:     {headline_imu:.3f} m/s   (uses sensed a_long)")
print(f"  Pedal+brake model:  {headline_model:.3f} m/s   (uses only commanded inputs)")

with open(f"{OUT}/summary_v3.json","w") as f:
    json.dump({
        "params": params,
        "horizon_s": HORIZON_S,
        "headline_v_mae_hold": headline_hold,
        "headline_v_mae_imu": headline_imu,
        "headline_v_mae_model": headline_model,
        "open_loop_test": ol.to_dict("records"),
        "closed_loop_agg_test": agg.to_dict("records"),
        "regime_test": reg_df.to_dict("records"),
    }, f, indent=2)
print(f"\nSaved {OUT}/summary_v3.json")
