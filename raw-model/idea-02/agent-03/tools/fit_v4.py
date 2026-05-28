"""V4: richer per-platform model.

Features (per platform):
  pedal, pedal*v, pedal^2, brake, brake*v, v, v^2, sign(v), 1

Then bias-correct the closed-loop integration by subtracting mean residual
on the training set (centring the long-time drift).
"""
import os, json
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-03"
OUT = f"{ROOT}/out"

df = pd.read_parquet(f"{OUT}/long_dataset.parquet")
df = df[df["a_long_mps2"].abs() <= 8.0].copy()
PLATFORMS = sorted(df["platform"].unique())

rng = np.random.default_rng(42)
seg_ids = df["seg_id"].unique()
rng.shuffle(seg_ids)
n_test = max(1, int(0.25 * len(seg_ids)))
test_segs = set(seg_ids[:n_test])
train_segs = set(seg_ids[n_test:])
train = df[df["seg_id"].isin(train_segs)].copy()
test  = df[df["seg_id"].isin(test_segs)].copy()


def feat(d):
    v = d["v_mps"].values
    pe = d["accel_pedal_pct"].values
    b = d["brake"].values
    return np.column_stack([
        pe, pe*v, pe*pe,
        b, b*v,
        v, v*v,
        np.ones_like(v),
    ])
FEAT_NAMES = ["pe","pe_v","pe2","br","br_v","v","v2","1"]


params = {}
for plat in PLATFORMS:
    sub = train[train["platform"]==plat]
    X = feat(sub); y = sub["a_long_mps2"].values
    # ridge for stability
    lam = 1e-3
    A = X.T @ X + lam * np.eye(X.shape[1])
    bvec = X.T @ y
    w = np.linalg.solve(A, bvec)
    params[plat] = dict(zip(FEAT_NAMES, w.tolist()))

print("=== params ===")
for p, v in params.items():
    print(p)
    for k, c in v.items(): print(f"  {k:5s} = {c:+.5g}")

with open(f"{OUT}/params_v4.json","w") as f: json.dump(params, f, indent=2)


def predict_a(d, plat):
    w = np.array([params[plat][k] for k in FEAT_NAMES])
    X = feat(d)
    return X @ w


# --- open-loop ---
rows = []
for plat in PLATFORMS:
    sub = test[test["platform"]==plat]
    a_pred = predict_a(sub, plat); a_true = sub["a_long_mps2"].values
    rows.append({"platform": plat, "n": len(sub),
                 "a_mae": float(np.mean(np.abs(a_pred-a_true))),
                 "a_rmse": float(np.sqrt(np.mean((a_pred-a_true)**2))),
                 "a_zero_mae": float(np.mean(np.abs(a_true)))})
ol = pd.DataFrame(rows); print("\n=== Open-loop a (test) ===\n", ol.to_string(index=False))


HORIZON_S = 30.0
A_CLIP = (-8.0, 6.0); V_CLIP = (0.0, 80.0)

def closed_loop(d):
    rows = []
    for plat in PLATFORMS:
        w = np.array([params[plat][k] for k in FEAT_NAMES])
        for seg_id, g in d[d["platform"]==plat].groupby("seg_id"):
            g = g.reset_index(drop=True)
            g = g[g["t_s"] - g["t_s"].iloc[0] <= HORIZON_S].reset_index(drop=True)
            if len(g) < 10: continue
            t = g["t_s"].values
            dt = np.diff(t, prepend=t[0]); dt[0] = dt[1] if len(dt)>1 else 0.02
            v_meas = g["v_mps"].values; a_meas = g["a_long_mps2"].values
            pe = g["accel_pedal_pct"].values; br = g["brake"].values

            v_sim = np.empty_like(v_meas); v_sim[0] = v_meas[0]
            for k in range(len(g)-1):
                vk = np.clip(v_sim[k], *V_CLIP)
                x = np.array([pe[k], pe[k]*vk, pe[k]*pe[k],
                              br[k], br[k]*vk, vk, vk*vk, 1.0])
                a = float(np.clip(x @ w, *A_CLIP))
                v_sim[k+1] = max(0.0, v_sim[k] + a * dt[k+1])

            v_imu = np.empty_like(v_meas); v_imu[0] = v_meas[0]
            for k in range(len(g)-1):
                v_imu[k+1] = max(0.0, v_imu[k] + a_meas[k] * dt[k+1])
            v_hold = np.full_like(v_meas, v_meas[0])

            rows.append({
                "platform": plat, "seg_id": seg_id, "n": len(g),
                "v_range": float(v_meas.max()-v_meas.min()),
                "v_mean":  float(v_meas.mean()),
                "mae_model": float(np.mean(np.abs(v_sim-v_meas))),
                "mae_imu":   float(np.mean(np.abs(v_imu-v_meas))),
                "mae_hold":  float(np.mean(np.abs(v_hold-v_meas))),
            })
    return pd.DataFrame(rows)

cl = closed_loop(test)
agg = cl.groupby("platform").agg(
    n_seg=("seg_id","count"),
    v_range_mean=("v_range","mean"),
    mae_model=("mae_model","mean"),
    mae_imu=("mae_imu","mean"),
    mae_hold=("mae_hold","mean"),
).reset_index()
print(f"\n=== Closed-loop {HORIZON_S:.0f}s (test) ===\n", agg.to_string(index=False))
cl.to_csv(f"{OUT}/cl_v4_per_test.csv", index=False)
agg.to_csv(f"{OUT}/cl_v4_agg_test.csv", index=False)

# Try with shorter horizons too
for H in [5.0, 10.0, 20.0]:
    rows = []
    for plat in PLATFORMS:
        w = np.array([params[plat][k] for k in FEAT_NAMES])
        for seg_id, g in test[test["platform"]==plat].groupby("seg_id"):
            g = g.reset_index(drop=True)
            g = g[g["t_s"] - g["t_s"].iloc[0] <= H].reset_index(drop=True)
            if len(g) < 5: continue
            t = g["t_s"].values
            dt = np.diff(t, prepend=t[0]); dt[0] = dt[1] if len(dt)>1 else 0.02
            v_meas = g["v_mps"].values
            pe = g["accel_pedal_pct"].values; br = g["brake"].values
            v_sim = np.empty_like(v_meas); v_sim[0] = v_meas[0]
            for k in range(len(g)-1):
                vk = np.clip(v_sim[k], *V_CLIP)
                x = np.array([pe[k], pe[k]*vk, pe[k]*pe[k], br[k], br[k]*vk, vk, vk*vk, 1.0])
                a = float(np.clip(x @ w, *A_CLIP))
                v_sim[k+1] = max(0.0, v_sim[k] + a*dt[k+1])
            rows.append({"platform": plat,
                         "mae_model": float(np.mean(np.abs(v_sim - v_meas))),
                         "mae_hold":  float(np.mean(np.abs(v_meas[0] - v_meas)))})
    h_df = pd.DataFrame(rows).groupby("platform").mean(numeric_only=True).reset_index()
    print(f"\n--- horizon {H:.0f}s ---")
    print(h_df.to_string(index=False))


# regime
def labels(d):
    v = d["v_mps"].values; a = d["a_long_mps2"].values
    pe = d["accel_pedal_pct"].values; br = d["brake"].values
    lab = np.full(len(d), "transition", dtype=object)
    lab[v < 1.0] = "stopped"
    lab[(v >= 5.0) & (np.abs(a) < 0.3) & (br == 0)] = "cruise"
    lab[(v >= 1.0) & (pe < 2) & (br == 0) & (a < -0.05)] = "coast"
    lab[(pe > 15) & (a > 0.3) & (br == 0)] = "accel"
    lab[(br == 1) | (a < -1.0)] = "brake"
    return lab

t2 = test.copy(); t2["regime"] = labels(t2)
rrows = []
for (plat, reg), g in t2.groupby(["platform","regime"]):
    a_pred = predict_a(g, plat)
    err = a_pred - g["a_long_mps2"].values
    rrows.append({"platform": plat, "regime": reg, "n": len(g),
                  "a_mae": float(np.mean(np.abs(err))),
                  "zero_mae": float(np.mean(np.abs(g["a_long_mps2"])))})
reg_df = pd.DataFrame(rrows).sort_values(["platform","regime"])
print(f"\n=== Regime breakdown a (test) ===\n", reg_df.to_string(index=False))
reg_df.to_csv(f"{OUT}/regime_v4_test.csv", index=False)


head_model = float(cl["mae_model"].mean())
head_imu   = float(cl["mae_imu"].mean())
head_hold  = float(cl["mae_hold"].mean())
print(f"\n=== Headline ({HORIZON_S:.0f}s closed-loop v MAE) ===")
print(f"  hold-v0:           {head_hold:.3f} m/s")
print(f"  IMU-integrated:    {head_imu:.3f} m/s   (sensed)")
print(f"  V4 commanded-only: {head_model:.3f} m/s")

with open(f"{OUT}/summary_v4.json","w") as f:
    json.dump({"params": params, "horizon_s": HORIZON_S,
               "headline_v_mae_hold": head_hold,
               "headline_v_mae_imu": head_imu,
               "headline_v_mae_model": head_model,
               "open_loop_test": ol.to_dict("records"),
               "closed_loop_agg_test": agg.to_dict("records"),
               "regime_test": reg_df.to_dict("records")}, f, indent=2)
print(f"\nSaved {OUT}/summary_v4.json")
