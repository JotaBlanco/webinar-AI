"""V2: piecewise longitudinal model with regime-specific fits.

Pieces:
  - Coasting (accel_pedal<2 AND brake_pressed==0):
        a_coast = -c0 - c1*v - c2*v^2          (rolling + linear + drag)
  - Power (accel_pedal>=2 AND brake_pressed==0):
        a_power = a_coast(v) + (k0 + k1*v)*accel_pedal_pct
  - Brake (brake_pressed==1):
        a_brake = a_coast(v) - b0
        (brake_pressed is binary so we can't get magnitude — single decel offset)

State: only v. Inputs at each step: accel_pedal_pct, brake_pressed (commanded).
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-06"
DATA = f"{ROOT}/data/sim/segments/FORD_MUSTANG_MACH_E_MK1"
OUT  = f"{ROOT}/out"
os.makedirs(OUT, exist_ok=True)


def load_segments():
    return sorted(glob.glob(f"{DATA}/*/*/*/sim.csv"))


def load_one(p):
    df = pd.read_csv(p)
    keep = ["t_s","v_mps","a_long_mps2","accel_pedal_pct","brake_pressed"]
    df = df[keep].dropna().reset_index(drop=True)
    return df


def fit_pieces(paths_train):
    # Aggregate samples
    Vs, As, APs, BPs = [], [], [], []
    for p in paths_train:
        df = load_one(p)
        if len(df) < 100: continue
        Vs.append(df["v_mps"].values)
        As.append(df["a_long_mps2"].values)
        APs.append(df["accel_pedal_pct"].values.astype(float))
        BPs.append(df["brake_pressed"].values.astype(float))
    v = np.concatenate(Vs); a = np.concatenate(As)
    ap = np.concatenate(APs); bp = np.concatenate(BPs)

    # Coast samples
    cm = (ap < 2) & (bp == 0)
    Xc = np.stack([np.ones_like(v[cm]), v[cm], v[cm]**2], axis=1)
    yc = a[cm]
    coast, *_ = np.linalg.lstsq(Xc, yc, rcond=None)
    # coast = [-c0, -c1, -c2] (so a_coast = coast @ [1, v, v^2])
    print(f"coast fit (n={cm.sum()}): a = {coast[0]:.4f} + {coast[1]:.4f}*v + {coast[2]:.5f}*v^2", file=sys.stderr)

    def a_coast_fn(vv):
        return coast[0] + coast[1]*vv + coast[2]*vv*vv

    # Power samples: a - a_coast(v) = (k0 + k1*v)*ap
    pm = (ap >= 2) & (bp == 0)
    residp = a[pm] - a_coast_fn(v[pm])
    Xp = np.stack([ap[pm], ap[pm]*v[pm]], axis=1)
    power, *_ = np.linalg.lstsq(Xp, residp, rcond=None)
    print(f"power fit (n={pm.sum()}): a_pow_extra = ({power[0]:.4f} + {power[1]:.5f}*v)*ap", file=sys.stderr)

    # Brake samples: a - a_coast(v) ~ -b0
    bm = (bp == 1)
    if bm.sum() > 10:
        residb = a[bm] - a_coast_fn(v[bm])
        b0 = -float(np.mean(residb))   # so a_brake = a_coast - b0
    else:
        b0 = 2.0
    print(f"brake fit (n={bm.sum()}): a_brake_extra = -{b0:.4f}", file=sys.stderr)

    return {"coast": coast.tolist(), "power": power.tolist(), "b0": b0}


def predict_a(v, ap, bp, model):
    coast = np.array(model["coast"])
    power = np.array(model["power"])
    b0 = model["b0"]
    a = coast[0] + coast[1]*v + coast[2]*v*v
    if bp >= 0.5:
        a = a - b0
    elif ap >= 2:
        a = a + (power[0] + power[1]*v)*ap
    return a


def integrate_closed_loop(df, model):
    t = df["t_s"].values
    ap = df["accel_pedal_pct"].values.astype(float)
    bp = df["brake_pressed"].values.astype(float)
    v_meas = df["v_mps"].values
    v = np.empty_like(v_meas)
    v[0] = v_meas[0]
    for i in range(1, len(t)):
        dt = t[i] - t[i-1]
        a = predict_a(v[i-1], ap[i-1], bp[i-1], model)
        v[i] = max(0.0, v[i-1] + a*dt)
    return v


def integrate_closed_loop_windowed(df, model, horizon_s=10.0):
    """Reset to measured v every horizon_s seconds; integrate predictions in between.
    Returns the concatenated predicted v across all windows.
    """
    t = df["t_s"].values
    ap = df["accel_pedal_pct"].values.astype(float)
    bp = df["brake_pressed"].values.astype(float)
    v_meas = df["v_mps"].values
    v = np.empty_like(v_meas)
    v[0] = v_meas[0]
    t0 = t[0]
    for i in range(1, len(t)):
        dt = t[i] - t[i-1]
        if (t[i-1] - t0) >= horizon_s:
            v[i-1] = v_meas[i-1]   # reset
            t0 = t[i-1]
        a = predict_a(v[i-1], ap[i-1], bp[i-1], model)
        v[i] = max(0.0, v[i-1] + a*dt)
    return v


def integrate_imu_baseline(df, horizon_s=None):
    t = df["t_s"].values
    a = df["a_long_mps2"].values
    v_meas = df["v_mps"].values
    v = np.empty_like(v_meas)
    v[0] = v_meas[0]
    t0 = t[0]
    for i in range(1, len(t)):
        dt = t[i] - t[i-1]
        if horizon_s is not None and (t[i-1] - t0) >= horizon_s:
            v[i-1] = v_meas[i-1]; t0 = t[i-1]
        v[i] = max(0.0, v[i-1] + a[i-1]*dt)
    return v


def one_step_a_pred(df, model):
    v = df["v_mps"].values
    ap = df["accel_pedal_pct"].values.astype(float)
    bp = df["brake_pressed"].values.astype(float)
    # vectorise
    coast = np.array(model["coast"]); power = np.array(model["power"]); b0 = model["b0"]
    a = coast[0] + coast[1]*v + coast[2]*v*v
    a = np.where(bp >= 0.5, a - b0, np.where(ap >= 2, a + (power[0] + power[1]*v)*ap, a))
    return a


def rmse(a, b):
    return float(np.sqrt(np.mean((a-b)**2)))


def main():
    paths = load_segments()
    print(f"Found {len(paths)} segments", file=sys.stderr)
    rng = np.random.default_rng(42)
    rng.shuffle(paths)
    n_train = int(0.7 * len(paths))
    train, test = paths[:n_train], paths[n_train:]

    model = fit_pieces(train)

    rows = []
    agg_pred, agg_null, agg_imu, agg_pred_w5, agg_pred_w10 = [], [], [], [], []
    agg_imu_w5, agg_imu_w10 = [], []
    agg_a_pred, agg_a_meas = [], []
    regime_pairs = {"cruise": [], "accel": [], "brake": [], "coast": [], "low_v": [], "high_v": []}
    for p in test:
        df = load_one(p)
        if len(df) < 100: continue
        v_meas = df["v_mps"].values
        v_pred = integrate_closed_loop(df, model)
        v_pred_w5 = integrate_closed_loop_windowed(df, model, 5.0)
        v_pred_w10 = integrate_closed_loop_windowed(df, model, 10.0)
        v_null = np.full_like(v_meas, v_meas[0])
        v_imu  = integrate_imu_baseline(df)
        v_imu_w5 = integrate_imu_baseline(df, 5.0)
        v_imu_w10 = integrate_imu_baseline(df, 10.0)
        a_pred_one = one_step_a_pred(df, model)
        a_meas = df["a_long_mps2"].values
        ap = df["accel_pedal_pct"].values
        bp = df["brake_pressed"].values
        a_long = df["a_long_mps2"].values

        rows.append({
            "path": p.replace(ROOT, "."),
            "n": len(df),
            "duration_s": float(df["t_s"].iloc[-1] - df["t_s"].iloc[0]),
            "v_mean": float(np.mean(v_meas)),
            "rmse_v_pred": rmse(v_meas, v_pred),
            "rmse_v_null": rmse(v_meas, v_null),
            "rmse_v_imu":  rmse(v_meas, v_imu),
            "rmse_a_one_step": rmse(a_pred_one, a_meas),
        })
        agg_pred.append((v_meas, v_pred))
        agg_pred_w5.append((v_meas, v_pred_w5))
        agg_pred_w10.append((v_meas, v_pred_w10))
        agg_null.append((v_meas, v_null))
        agg_imu.append((v_meas, v_imu))
        agg_imu_w5.append((v_meas, v_imu_w5))
        agg_imu_w10.append((v_meas, v_imu_w10))
        agg_a_pred.append(a_pred_one); agg_a_meas.append(a_meas)

        err = v_pred - v_meas
        masks = {
            "cruise":   (ap < 5) & (bp == 0) & (np.abs(a_long) < 0.3),
            "accel":    (ap >= 5) & (bp == 0),
            "brake":    (bp == 1),
            "coast":    (ap < 5) & (bp == 0) & (a_long < -0.3),
            "low_v":    (v_meas < 5),
            "high_v":   (v_meas > 20),
        }
        for k, m in masks.items():
            if m.sum() > 0:
                regime_pairs[k].append((v_meas[m], v_pred[m]))

    def agg_rmse(pairs):
        sq = []
        for vm, vp in pairs:
            sq.append((vp - vm)**2)
        return float(np.sqrt(np.mean(np.concatenate(sq))))

    summary = {
        "test_segments": len(rows),
        "primary_metric": "closed_loop_v_rmse_mps_aggregated_over_all_test_samples",
        "rmse_aggregate_mps": {
            "fitted_model_closed_loop_full_segment": agg_rmse(agg_pred),
            "fitted_model_closed_loop_10s_horizon":  agg_rmse(agg_pred_w10),
            "fitted_model_closed_loop_5s_horizon":   agg_rmse(agg_pred_w5),
            "null_constant_v0":                       agg_rmse(agg_null),
            "imu_integrated_baseline_full_segment":   agg_rmse(agg_imu),
            "imu_integrated_baseline_10s_horizon":    agg_rmse(agg_imu_w10),
            "imu_integrated_baseline_5s_horizon":     agg_rmse(agg_imu_w5),
        },
        "one_step_a_rmse_mps2": {
            "fitted_model": rmse(np.concatenate(agg_a_pred), np.concatenate(agg_a_meas)),
        },
        "model_coefficients": model,
        "regime_closed_loop_rmse_mps": {
            k: {"n": int(sum(len(vm) for vm,_ in pairs)),
                "rmse": agg_rmse(pairs)} if pairs else None
            for k, pairs in regime_pairs.items()
        },
    }

    pd.DataFrame(rows).to_csv(f"{OUT}/per_segment_metrics_v2.csv", index=False)
    with open(f"{OUT}/summary_v2.json","w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
