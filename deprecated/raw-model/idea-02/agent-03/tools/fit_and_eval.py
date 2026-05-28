"""Fit a simple physics-motivated longitudinal model and evaluate it
in open-loop one-step and closed-loop integration modes.

Model:
    a_pred = c_throttle * pedal_pct
           + c_brake    * brake_indicator * v          # brake torque ~ proportional to v (rough)
           + c_brake0   * brake_indicator              # brake bias
           - c_drag     * v**2                          # aero drag
           - c_roll     * v                             # rolling/coast
           + bias

Per-platform parameters (Tesla / Mach-E / F-150 differ in mass, drag, regen).

Baseline = predict a_pred = 0 (vehicle coasts at constant v).
"""
import os
import json
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression  # if missing, fall back

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-03"
OUT = f"{ROOT}/out"

df = pd.read_parquet(f"{OUT}/long_dataset.parquet")
print(f"Loaded {len(df):,} rows, {df['seg_id'].nunique()} segments")

PLATFORMS = sorted(df["platform"].unique())

# Train/test split by segment so we don't leak within-segment.
rng = np.random.default_rng(42)
seg_ids = df["seg_id"].unique()
rng.shuffle(seg_ids)
n_test = max(1, int(0.25 * len(seg_ids)))
test_segs = set(seg_ids[:n_test])
train_segs = set(seg_ids[n_test:])

train = df[df["seg_id"].isin(train_segs)].copy()
test  = df[df["seg_id"].isin(test_segs)].copy()
print(f"Train segs={len(train_segs)} ({len(train):,} rows)  Test segs={len(test_segs)} ({len(test):,} rows)")


def features(d):
    v = d["v_mps"].values
    p = d["accel_pedal_pct"].values
    b = d["brake"].values
    return np.column_stack([
        p,           # throttle term
        b * v,       # brake * v
        b,           # brake bias
        v * v,       # drag
        v,           # rolling
    ])


# ---------- fit per platform ----------
params = {}
for plat in PLATFORMS:
    sub = train[train["platform"] == plat]
    if len(sub) < 1000:
        continue
    X = features(sub)
    y = sub["a_long_mps2"].values
    reg = LinearRegression().fit(X, y)
    coefs = reg.coef_.tolist()
    intercept = reg.intercept_
    params[plat] = {
        "c_throttle": coefs[0],
        "c_brake_v": coefs[1],
        "c_brake0": coefs[2],
        "c_drag": -coefs[3],   # stored as positive drag coeff
        "c_roll": -coefs[4],
        "bias": intercept,
    }
    print(f"\n{plat}: {params[plat]}")

with open(f"{OUT}/params.json", "w") as f:
    json.dump(params, f, indent=2)


def predict_a(d, plat):
    p = params[plat]
    v = d["v_mps"].values
    pe = d["accel_pedal_pct"].values
    b = d["brake"].values
    return (p["c_throttle"] * pe
            + p["c_brake_v"] * b * v
            + p["c_brake0"] * b
            - p["c_drag"] * v * v
            - p["c_roll"] * v
            + p["bias"])


# ---------- open-loop one-step a_long MAE / RMSE ----------
def open_loop_metrics(d, label):
    rows = []
    for plat in PLATFORMS:
        sub = d[d["platform"] == plat]
        if not len(sub):
            continue
        a_pred = predict_a(sub, plat)
        a_true = sub["a_long_mps2"].values
        err = a_pred - a_true
        rows.append({
            "platform": plat,
            "n": len(sub),
            "a_mae": float(np.mean(np.abs(err))),
            "a_rmse": float(np.sqrt(np.mean(err ** 2))),
            "a_baseline_mae": float(np.mean(np.abs(a_true))),   # baseline = predict 0
        })
    out = pd.DataFrame(rows)
    print(f"\n=== Open-loop (one-step a_long) metrics on {label} ===")
    print(out.to_string(index=False))
    return out


open_loop_metrics(train, "train")
ol_test = open_loop_metrics(test, "test")
ol_test.to_csv(f"{OUT}/open_loop_metrics_test.csv", index=False)


# ---------- closed-loop integration ----------
# For each test segment, start at v0 = measured v[0], integrate
# v[k+1] = v[k] + a_pred(v[k], pedal[k], brake[k]) * dt
# Then compute MAE over the full horizon.
# Baseline = "constant-speed" (v_pred[k] = v0).

HORIZON_S = 30.0   # cap horizon

def closed_loop_eval(d, label):
    rows = []
    per_seg = []
    for plat in PLATFORMS:
        sub = d[d["platform"] == plat]
        for seg_id, g in sub.groupby("seg_id"):
            g = g.reset_index(drop=True)
            # truncate to first HORIZON_S seconds for fair comparison
            mask = g["t_s"] - g["t_s"].iloc[0] <= HORIZON_S
            g = g[mask].reset_index(drop=True)
            if len(g) < 10:
                continue
            dt = np.diff(g["t_s"].values, prepend=g["t_s"].values[0])
            dt[0] = dt[1] if len(dt) > 1 else 0.02
            v_meas = g["v_mps"].values
            pe = g["accel_pedal_pct"].values
            br = g["brake"].values

            # Roll forward
            v_sim = np.zeros_like(v_meas)
            v_sim[0] = v_meas[0]
            p = params[plat]
            for k in range(len(g) - 1):
                a = (p["c_throttle"] * pe[k]
                     + p["c_brake_v"] * br[k] * v_sim[k]
                     + p["c_brake0"] * br[k]
                     - p["c_drag"] * v_sim[k] ** 2
                     - p["c_roll"] * v_sim[k]
                     + p["bias"])
                v_sim[k + 1] = max(0.0, v_sim[k] + a * dt[k + 1])

            v_baseline = np.full_like(v_meas, v_meas[0])

            mae_model = float(np.mean(np.abs(v_sim - v_meas)))
            mae_base  = float(np.mean(np.abs(v_baseline - v_meas)))
            per_seg.append({"platform": plat, "seg_id": seg_id, "n": len(g),
                            "mae_model": mae_model, "mae_base": mae_base})
    out = pd.DataFrame(per_seg)
    agg = (out.groupby("platform")
              .agg(n_seg=("seg_id", "count"),
                   v_mae_model=("mae_model", "mean"),
                   v_mae_base=("mae_base", "mean"))
              .reset_index())
    print(f"\n=== Closed-loop ({HORIZON_S:.0f}s horizon) on {label} ===")
    print(agg.to_string(index=False))
    return out, agg


cl_per, cl_agg = closed_loop_eval(test, "test")
cl_per.to_csv(f"{OUT}/closed_loop_per_seg_test.csv", index=False)
cl_agg.to_csv(f"{OUT}/closed_loop_agg_test.csv", index=False)


# ---------- regime breakdown ----------
def regime_label(row):
    if row.brake > 0.5:
        return "brake"
    if row.accel_pedal_pct > 15 and row.v_mps > 1:
        return "accel"
    if row.accel_pedal_pct < 2 and row.v_mps > 1:
        return "coast"
    if row.v_mps < 1:
        return "stopped"
    return "cruise"

def regime_metrics(d, label):
    d = d.copy()
    d["regime"] = d.apply(regime_label, axis=1)
    rows = []
    for (plat, reg), g in d.groupby(["platform", "regime"]):
        a_pred = predict_a(g, plat)
        err = a_pred - g["a_long_mps2"].values
        rows.append({"platform": plat, "regime": reg, "n": len(g),
                     "a_mae": float(np.mean(np.abs(err))),
                     "a_rmse": float(np.sqrt(np.mean(err ** 2))),
                     "a_baseline_mae": float(np.mean(np.abs(g["a_long_mps2"])))})
    out = pd.DataFrame(rows).sort_values(["platform", "regime"])
    print(f"\n=== Regime breakdown (open-loop a_long) on {label} ===")
    print(out.to_string(index=False))
    return out

# Subsample for speed on regime breakdown (apply is slow)
test_sample = test.sample(min(60000, len(test)), random_state=0)
reg_out = regime_metrics(test_sample, "test (subsample 60k)")
reg_out.to_csv(f"{OUT}/regime_metrics_test.csv", index=False)


# ---------- Save summary ----------
summary = {
    "n_train_rows": int(len(train)),
    "n_test_rows": int(len(test)),
    "n_train_segs": len(train_segs),
    "n_test_segs": len(test_segs),
    "horizon_s": HORIZON_S,
    "open_loop_test": ol_test.to_dict("records"),
    "closed_loop_agg_test": cl_agg.to_dict("records"),
    "regime_test": reg_out.to_dict("records"),
    "params": params,
}
with open(f"{OUT}/summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print(f"\nSaved summary -> {OUT}/summary.json")
