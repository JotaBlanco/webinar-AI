"""Fit a standalone longitudinal speed model for Ford Mach-E.

Model form (per-axle "effective force" -> acceleration):
    a_pred(t) = k_accel * accel_pedal_pct / (1 + alpha*v)     # powertrain torque w/ falloff
              - k_brake * brake_pressed                        # constant brake decel when applied
              - c_drag * v^2                                   # aero drag
              - c_roll                                         # rolling resistance + grade bias

State: only v. dv/dt = a_pred.

Inputs at every step:
    - accel_pedal_pct  (driver-commanded)
    - brake_pressed    (driver-commanded, binary)
    - v                (the model's own state - NOT measured)

We fit on a training split via least squares on instantaneous a_long_meas,
then validate by closed-loop integration of dv/dt = a_pred(v, u(t)) on a
held-out split, comparing predicted v(t) against measured v(t).

Baselines for comparison:
  B0: v(t) = v(0)            (constant-speed null model)
  B1: integrate dv/dt = a_long_meas (IMU)  -- removes clamp, uses measured a only.
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
    paths = sorted(glob.glob(f"{DATA}/*/*/*/sim.csv"))
    return paths


def load_one(p):
    df = pd.read_csv(p)
    keep = ["t_s","v_mps","a_long_mps2","accel_pedal_pct","brake_pressed"]
    df = df[keep].dropna().reset_index(drop=True)
    return df


def build_design(df):
    v = df["v_mps"].values
    ap = df["accel_pedal_pct"].values.astype(float)
    bp = df["brake_pressed"].values.astype(float)
    # Regressors:
    #   c1*accel_pedal_pct                (constant torque-per-pedal)
    #   c2*accel_pedal_pct*v              (allows linear falloff with v)
    #   c3*brake_pressed                  (negative when fit)
    #   c4*v^2                            (drag)
    #   c5                                (rolling + bias)
    X = np.stack([ap, ap*v, bp, v*v, np.ones_like(v)], axis=1)
    y = df["a_long_mps2"].values
    return X, y


def fit(paths_train):
    X_all, y_all = [], []
    for p in paths_train:
        df = load_one(p)
        if len(df) < 100: continue
        X, y = build_design(df)
        X_all.append(X); y_all.append(y)
    X = np.vstack(X_all); y = np.concatenate(y_all)
    # OLS
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return coef


def predict_a(v, ap, bp, coef):
    c1, c2, c3, c4, c5 = coef
    return c1*ap + c2*ap*v + c3*bp + c4*v*v + c5


def integrate_closed_loop(df, coef):
    """Integrate dv/dt = predict_a(v, ap(t), bp(t)) using only commanded inputs."""
    t = df["t_s"].values
    ap = df["accel_pedal_pct"].values.astype(float)
    bp = df["brake_pressed"].values.astype(float)
    v_meas = df["v_mps"].values
    v_pred = np.empty_like(v_meas)
    v_pred[0] = v_meas[0]
    for i in range(1, len(t)):
        dt = t[i] - t[i-1]
        # forward Euler at left endpoint with current commanded inputs
        a = predict_a(v_pred[i-1], ap[i-1], bp[i-1], coef)
        v_new = v_pred[i-1] + a*dt
        v_pred[i] = max(0.0, v_new)
    return v_pred


def one_step_a_metrics(df, coef):
    """Open-loop one-step: a_pred(v_meas[t], u[t]) vs a_meas[t]."""
    v = df["v_mps"].values
    ap = df["accel_pedal_pct"].values.astype(float)
    bp = df["brake_pressed"].values.astype(float)
    a_meas = df["a_long_mps2"].values
    a_pred = predict_a(v, ap, bp, coef)
    err = a_pred - a_meas
    return float(np.sqrt(np.mean(err**2))), float(np.mean(np.abs(err))), a_pred, a_meas


def integrate_imu_baseline(df):
    """Baseline B1: dv/dt = a_long_meas (IMU). No driver inputs used."""
    t = df["t_s"].values
    a = df["a_long_mps2"].values
    v_meas = df["v_mps"].values
    v = np.empty_like(v_meas)
    v[0] = v_meas[0]
    for i in range(1, len(t)):
        dt = t[i] - t[i-1]
        v_new = v[i-1] + a[i-1]*dt
        v[i] = max(0.0, v_new)
    return v


def metrics(v_meas, v_pred):
    err = v_pred - v_meas
    rmse = float(np.sqrt(np.mean(err**2)))
    mae = float(np.mean(np.abs(err)))
    mx  = float(np.max(np.abs(err)))
    return {"rmse_mps": rmse, "mae_mps": mae, "max_abs_mps": mx}


def regime_breakdown(df, v_pred):
    v_meas = df["v_mps"].values
    ap = df["accel_pedal_pct"].values
    bp = df["brake_pressed"].values
    a = df["a_long_mps2"].values
    err = v_pred - v_meas
    masks = {
        "cruise":   (ap < 5) & (bp == 0) & (np.abs(a) < 0.3),
        "accel":    (ap >= 5) & (bp == 0),
        "brake":    (bp == 1),
        "coast":    (ap < 5) & (bp == 0) & (a < -0.3),
        "low_v":    (v_meas < 5),
        "high_v":   (v_meas > 20),
    }
    out = {}
    for name, m in masks.items():
        if m.sum() < 5:
            out[name] = None
        else:
            out[name] = {
                "n": int(m.sum()),
                "rmse_mps": float(np.sqrt(np.mean(err[m]**2))),
                "mae_mps":  float(np.mean(np.abs(err[m]))),
            }
    return out


def main():
    paths = load_segments()
    print(f"Found {len(paths)} Mach-E sim segments", file=sys.stderr)
    rng = np.random.default_rng(42)
    rng.shuffle(paths)
    n_train = int(0.7 * len(paths))
    train, test = paths[:n_train], paths[n_train:]
    print(f"Train: {len(train)}  Test: {len(test)}", file=sys.stderr)

    coef = fit(train)
    print(f"Fitted coefficients (c1*ap + c2*ap*v + c3*bp + c4*v^2 + c5):", file=sys.stderr)
    print(f"  {coef}", file=sys.stderr)

    rows = []
    agg_pred = []
    agg_null = []
    agg_imu = []
    regime_acc = {}
    for p in test:
        df = load_one(p)
        if len(df) < 100: continue
        v_meas = df["v_mps"].values
        v_pred = integrate_closed_loop(df, coef)
        v_null = np.full_like(v_meas, v_meas[0])
        v_imu  = integrate_imu_baseline(df)
        m_pred = metrics(v_meas, v_pred)
        m_null = metrics(v_meas, v_null)
        m_imu  = metrics(v_meas, v_imu)
        rows.append({
            "path": p.replace(ROOT, "."),
            "n": len(df),
            "duration_s": float(df["t_s"].iloc[-1] - df["t_s"].iloc[0]),
            "v_mean": float(np.mean(v_meas)),
            "rmse_pred": m_pred["rmse_mps"],
            "rmse_null": m_null["rmse_mps"],
            "rmse_imu":  m_imu["rmse_mps"],
        })
        agg_pred.append((v_meas, v_pred))
        agg_null.append((v_meas, v_null))
        agg_imu.append((v_meas, v_imu))
        rb = regime_breakdown(df, v_pred)
        for k, vstat in rb.items():
            if vstat is None: continue
            if k not in regime_acc:
                regime_acc[k] = {"n": 0, "se": 0.0, "ae": 0.0}
            regime_acc[k]["n"]  += vstat["n"]
            regime_acc[k]["se"] += vstat["rmse_mps"]**2 * vstat["n"]
            regime_acc[k]["ae"] += vstat["mae_mps"]   * vstat["n"]

    def agg_rmse(pairs):
        sq = []
        for vm, vp in pairs:
            sq.append((vp - vm)**2)
        all_sq = np.concatenate(sq)
        return float(np.sqrt(np.mean(all_sq)))

    agg = {
        "test_segments": len(rows),
        "rmse_aggregate_mps": {
            "fitted_model": agg_rmse(agg_pred),
            "null_constant_v0": agg_rmse(agg_null),
            "imu_integrated_baseline": agg_rmse(agg_imu),
        },
        "coefficients": {
            "k_accel_per_pct":   float(coef[0]),
            "k_accel_v_coupling":float(coef[1]),
            "k_brake_constant":  float(coef[2]),
            "c_drag_v2":         float(coef[3]),
            "c_bias":            float(coef[4]),
        },
        "regime_rmse_mps": {
            k: {"n": v["n"],
                "rmse": float(np.sqrt(v["se"]/v["n"])),
                "mae":  float(v["ae"]/v["n"])}
            for k, v in regime_acc.items()
        },
    }

    pd.DataFrame(rows).to_csv(f"{OUT}/per_segment_metrics.csv", index=False)
    with open(f"{OUT}/summary.json","w") as f:
        json.dump(agg, f, indent=2)
    print(json.dumps(agg, indent=2))


if __name__ == "__main__":
    main()
