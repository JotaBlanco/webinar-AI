"""Build a longitudinal model that predicts v_mps without using measured v.

Inputs (commanded / actuator-side):
  - accel_pedal_pct (commanded)
  - brake_pedal_state (commanded, enum)
  - di_torque_actual_nm (sensed actuator torque — closest stand-in for the
    commanded torque the powertrain inverter realised)

Output predicted (sensed): v_mps

We compare two longitudinal models:
  M0: identity-acceleration baseline — predict a_long_mps2 = 0 and integrate.
  M1: linear regression a_pred = b0 + b1*T_mot + b2*pedal + b3*brake_on + b4*v + b5*v^2
       integrated forward in closed loop.
  M2: physics-form a_pred = (k_T*T_mot - c0 - c_rr*v - c_a*v^2 - k_b*brake_on*v) / m
       where m is the known vehicle mass and (k_T, c0, c_rr, c_a, k_b) are
       least-squares fit to measured a_long.

We evaluate two ways:
  - open-loop one-step:  RMSE of a_pred vs a_meas (no integration)
  - closed-loop full segment: integrate v(t) from v(0) using a_pred(v_pred, u_t)
    and measure RMSE / MAE / final-speed-error vs v_meas. Report per-regime.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-04")
SIM_ROOT = ROOT / "data" / "sim" / "segments" / "TESLA_MODEL_3"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

# Vehicle mass (kg) from parameters.py (openpilot-canonical Tesla M3 LR AWD).
M_TESLA = 2035.0


def collect_segments(max_files: int | None = None):
    csvs = sorted(SIM_ROOT.rglob("sim.csv"))
    if max_files is not None:
        csvs = csvs[:max_files]
    return csvs


def regime_label(v, a, brake_on, pedal):
    """Mutually-exclusive regime label per sample.
    NOTE: brake_pedal_state was always INVALID(=2) in this dataset, so we infer
    braking purely from negative acceleration. See SURPRISES in report.
    Priority order: stop > brake > accel > coast > cruise > other.
    """
    out = np.full(len(v), "other", dtype=object)
    # cruise first (low priority — easy regime)
    out[(np.abs(a) < 0.3) & (v > 2.0)] = "cruise"
    # coast: no throttle, mild decel
    coast = (pedal < 3) & (a < 0.0) & (a > -0.5) & (v > 2.0)
    out[coast] = "coast"
    # accel
    accel = (a > 0.4) & (pedal > 3)
    out[accel] = "accel"
    # brake (inferred): strong deceleration
    brake = (a < -0.6)
    out[brake] = "brake"
    # stop: ~zero speed
    out[v < 0.5] = "stop"
    return out


def load_all(csvs):
    dfs = []
    seg_ids = []
    for i, c in enumerate(csvs):
        try:
            df = pd.read_csv(c)
        except Exception:
            continue
        df["seg_id"] = i
        df["seg_path"] = str(c)
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True), [str(c) for c in csvs]


def fit_linear(X, y):
    # ordinary least squares with bias term included via design matrix
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return coef


def design_M1(df):
    v = df["v_mps"].values
    T = df["di_torque_actual_nm"].values
    pedal = df["accel_pedal_pct"].values
    brake = (df["brake_pedal_state"].values > 1).astype(float)
    n = len(v)
    X = np.column_stack([
        np.ones(n), T, pedal, brake, v, v * v
    ])
    y = df["a_long_mps2"].values
    return X, y


def design_M2(df):
    # a*m = k_T*T - c0 - c_rr*v - c_a*v^2 - k_b*brake_on*v
    # fit unknowns: [k_T, c0, c_rr, c_a, k_b]
    v = df["v_mps"].values
    T = df["di_torque_actual_nm"].values
    brake = (df["brake_pedal_state"].values > 1).astype(float)
    n = len(v)
    # Rearranged: a*m = k_T*T + (-1)*c0 + (-v)*c_rr + (-v^2)*c_a + (-brake*v)*k_b
    X = np.column_stack([
        T,
        -np.ones(n),
        -v,
        -v * v,
        -brake * v,
    ])
    y = df["a_long_mps2"].values * M_TESLA
    return X, y


def predict_a_M1(coef, T, pedal, brake_on, v):
    return (coef[0] + coef[1] * T + coef[2] * pedal + coef[3] * brake_on
            + coef[4] * v + coef[5] * v * v)


def predict_a_M2(coef, T, brake_on, v):
    k_T, c0, c_rr, c_a, k_b = coef
    return (k_T * T - c0 - c_rr * v - c_a * v * v - k_b * brake_on * v) / M_TESLA


def integrate_closed_loop(df, predict_fn):
    """Forward-Euler integration of v from v(0) using predicted accel.
    Inputs at each step are taken from the segment (commanded actuator side):
    pedal, brake_on, motor torque. Note: motor torque is the realised actuator
    output, not a pure command — best available stand-in.
    """
    t = df["t_s"].values
    dt = np.diff(t, prepend=t[0])  # first dt = 0 so v[0]=v_meas[0]
    v_pred = np.empty_like(t, dtype=float)
    v_pred[0] = df["v_mps"].iloc[0]
    T = df["di_torque_actual_nm"].values
    pedal = df["accel_pedal_pct"].values
    brake = (df["brake_pedal_state"].values > 1).astype(float)
    for k in range(len(t) - 1):
        a = predict_fn(T[k], pedal[k], brake[k], v_pred[k])
        v_pred[k + 1] = max(0.0, v_pred[k] + a * (t[k + 1] - t[k]))
    return v_pred


def main():
    csvs = collect_segments(max_files=200)  # speed: use 200 segments
    print(f"Loading {len(csvs)} segments...")
    df_all, seg_paths = load_all(csvs)
    print(f"Rows total: {len(df_all)}")
    # 80/20 split by segment id (chronological order)
    seg_ids = df_all["seg_id"].unique()
    rng = np.random.default_rng(0)
    rng.shuffle(seg_ids)
    n_train = int(0.8 * len(seg_ids))
    train_ids = set(seg_ids[:n_train].tolist())
    test_ids  = set(seg_ids[n_train:].tolist())
    df_train = df_all[df_all["seg_id"].isin(train_ids)].copy()
    df_test  = df_all[df_all["seg_id"].isin(test_ids)].copy()

    # ---- Fit M1 (linear) and M2 (physics) on train ----
    X1, y1 = design_M1(df_train)
    coef1 = fit_linear(X1, y1)
    print("M1 coefficients [bias, T, pedal, brake, v, v^2]:", coef1)

    X2, y2 = design_M2(df_train)
    coef2 = fit_linear(X2, y2)
    print("M2 coefficients [k_T, c0, c_rr, c_a, k_b]:", coef2)

    # ---- Open-loop one-step on test ----
    a_meas = df_test["a_long_mps2"].values
    a_M0 = np.zeros_like(a_meas)
    T_te = df_test["di_torque_actual_nm"].values
    p_te = df_test["accel_pedal_pct"].values
    b_te = (df_test["brake_pedal_state"].values > 1).astype(float)
    v_te = df_test["v_mps"].values
    a_M1 = predict_a_M1(coef1, T_te, p_te, b_te, v_te)
    a_M2 = predict_a_M2(coef2, T_te, b_te, v_te)

    def rmse(a, b):
        return float(np.sqrt(np.mean((a - b) ** 2)))

    res = {
        "open_loop_one_step_a_RMSE_mps2": {
            "M0_zero":   rmse(a_meas, a_M0),
            "M1_linear": rmse(a_meas, a_M1),
            "M2_phys":   rmse(a_meas, a_M2),
        }
    }

    # ---- Closed-loop integration per test segment ----
    cl_full = {"M0": [], "M1": [], "M2": []}
    cl_short = {"M0": [], "M1": [], "M2": []}  # 10s windows, reset v_pred each
    # per-regime: collect squared errors per regime per model
    regime_errs = {m: {r: [] for r in ("cruise", "accel", "brake", "coast", "stop", "other")} for m in ("M0", "M1", "M2")}
    SHORT = 500  # samples; 50 Hz x 10s = 500

    for sid, g in df_test.groupby("seg_id"):
        g = g.reset_index(drop=True)
        v_meas = g["v_mps"].values
        v_M0_full = np.full_like(v_meas, v_meas[0])
        v_M1_full = integrate_closed_loop(g, lambda T,p,b,v: predict_a_M1(coef1, T,p,b,v))
        v_M2_full = integrate_closed_loop(g, lambda T,p,b,v: predict_a_M2(coef2, T,b,v))
        for name, vpred in (("M0", v_M0_full), ("M1", v_M1_full), ("M2", v_M2_full)):
            cl_full[name].append(rmse(v_meas, vpred))

        # Short closed-loop: split into 10s windows, integrate each independently
        for start in range(0, len(g) - 50, SHORT):
            end = min(start + SHORT, len(g))
            gw = g.iloc[start:end].reset_index(drop=True)
            if len(gw) < 50:
                continue
            vw_meas = gw["v_mps"].values
            v_M0w = np.full_like(vw_meas, vw_meas[0])
            v_M1w = integrate_closed_loop(gw, lambda T,p,b,v: predict_a_M1(coef1, T,p,b,v))
            v_M2w = integrate_closed_loop(gw, lambda T,p,b,v: predict_a_M2(coef2, T,b,v))
            for name, vpred in (("M0", v_M0w), ("M1", v_M1w), ("M2", v_M2w)):
                cl_short[name].append(rmse(vw_meas, vpred))
                # regime errors using a_long ground truth
                a_long = gw["a_long_mps2"].values
                brake_state = gw["brake_pedal_state"].values
                pedal = gw["accel_pedal_pct"].values
                reg = regime_label(vw_meas, a_long, brake_state, pedal)
                err2 = (vw_meas - vpred) ** 2
                for r in ("cruise", "accel", "brake", "coast", "stop", "other"):
                    mask = reg == r
                    if mask.any():
                        regime_errs[name][r].extend(err2[mask].tolist())

    res["closed_loop_full_seg_v_RMSE_mps_mean"] = {k: float(np.mean(v)) for k, v in cl_full.items()}
    res["closed_loop_full_seg_v_RMSE_mps_median"] = {k: float(np.median(v)) for k, v in cl_full.items()}
    res["closed_loop_10s_v_RMSE_mps_mean"] = {k: float(np.mean(v)) for k, v in cl_short.items()}
    res["closed_loop_10s_v_RMSE_mps_median"] = {k: float(np.median(v)) for k, v in cl_short.items()}
    res["regime_v_RMSE_mps_10s"] = {
        m: {r: (float(np.sqrt(np.mean(e))) if e else None) for r, e in d.items()}
        for m, d in regime_errs.items()
    }
    res["n_train_segments"] = len(train_ids)
    res["n_test_segments"] = len(test_ids)

    (OUT / "long_model_metrics.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
