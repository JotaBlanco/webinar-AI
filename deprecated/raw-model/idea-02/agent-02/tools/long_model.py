"""Longitudinal model: predict v_mps without using it as an input.

Strategy
--------
The current KS model takes measured `v` as an input (the "crutch").  We
remove it by building a model that predicts longitudinal acceleration
`a` from *commanded / observable* signals, then integrates to get v.

Inputs we treat as legitimate (no measured v):
  - accel_pedal_pct          (driver command, %)
  - brake_pressed            (driver command, bool)
  - current predicted v      (model state, NOT measured)

Inputs we forbid (those are the crutches):
  - v_mps (measured speed)   — the channel we're trying to predict
  - a_long_mps2 (IMU accel)  — sensed downstream of the powertrain; using
                                this would just shift the crutch one layer
                                down.

Model form (simple, physics-shaped):
    a_pred(t) = c_p * accel_pct(t)
              + c_b * brake_pressed(t) * v_state(t)   (brake decel scales with v)
              - r_v * v_state(t)                       (lumped drag/rolling)
              - r_v2 * v_state(t)^2                    (aero drag)
              + c0                                     (grade / regen bias)

Fit by least squares on (a_long_mps2 as the target) — since IMU long accel
is forbidden as a runtime input, but is fine as a *fit target* because we
only need it offline once to learn coefficients.

Validation
----------
  - open-loop one-step:   a_pred vs a_long_meas at each tick   → MAE on a
  - closed-loop integrate: forward-Euler v_pred from a_pred over the whole
    segment (initial v_pred = v_meas[0]).  Compare v_pred vs v_meas.
    Horizon = full segment length (typically ~60 s).

Baselines for headline number
-----------------------------
  Baseline 0 ("the crutch"): v_pred(t) := v_meas(t)               → RMSE 0
  Baseline 1 ("integrate sensed IMU a"): v_pred = v0 + ∫ a_meas dt → drift
  Our model :                       v_pred = v0 + ∫ a_pred dt     → target
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
from load_segments import stack_all, find_csvs, load_segment


# ---------------- helpers ----------------------------------------------

def regime_labels(df: pd.DataFrame) -> pd.Series:
    """Tag every sample with a regime label."""
    v = df["v_mps"].values
    a = df["a_long_mps2"].values
    bp = df["brake_pressed"].values
    ap = df["accel_pedal_pct"].values
    label = np.full(len(df), "cruise", dtype=object)
    label[(a > 0.5) & (ap > 5)]   = "accel"
    label[(a < -0.5) & (bp > 0.5)] = "brake"
    label[(a < -0.3) & (bp <= 0.5) & (ap < 2)] = "coast"
    label[v < 1.0] = "stop"
    return pd.Series(label, index=df.index, name="regime")


# ---------------- model ------------------------------------------------

def features(df: pd.DataFrame, v_col: str = "v_mps") -> np.ndarray:
    """Build feature matrix X for the linear model.

    Columns: [accel_pct, accel_pct*v, brake*v, v, sign(v)*v^2, 1]
      - accel_pct*v captures the torque-falls-off-with-speed shape (EV motors)
      - sign(v)*v^2 is the aero-drag term; sign keeps it opposing motion
    """
    ap = df["accel_pedal_pct"].values
    bp = df["brake_pressed"].values
    v  = df[v_col].values
    return np.column_stack([
        ap,                          # throttle
        ap * v,                      # throttle*v  (torque sag)
        bp * v,                      # brake decel scales with speed
        v,                           # rolling resistance / friction (linear in v)
        -np.sign(v) * v * v,         # aero drag (always opposes motion)
        np.ones_like(v),
    ])


def fit(df_train: pd.DataFrame) -> np.ndarray:
    X = features(df_train)
    y = df_train["a_long_mps2"].values
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return coef


def predict_a(df: pd.DataFrame, coef: np.ndarray, v_col: str = "v_mps") -> np.ndarray:
    return features(df, v_col=v_col) @ coef


# ---------------- closed-loop integrator -------------------------------

def closed_loop_segment(seg: pd.DataFrame, coef: np.ndarray) -> pd.DataFrame:
    """Integrate v_pred over a single segment using only commanded inputs.

    State: v_pred (starts at v_meas[0]).  At each tick we recompute features
    using v_pred (NOT v_meas), predict a, and integrate forward-Euler.
    """
    t   = seg["t_s"].values
    ap  = seg["accel_pedal_pct"].values
    bp  = seg["brake_pressed"].values
    v0  = float(seg["v_mps"].iloc[0])
    N = len(seg)
    v_pred = np.empty(N)
    a_pred = np.empty(N)
    v_pred[0] = v0
    cP, cPv, cB, rV, kAero, c0 = coef
    V_CAP = 50.0  # m/s — physical sanity cap (~180 km/h)
    for k in range(N - 1):
        v = v_pred[k]
        a = (cP * ap[k]
             + cPv * ap[k] * v
             + cB * bp[k] * v
             + rV * v
             - kAero * np.sign(v) * v * v
             + c0)
        a_pred[k] = a
        dt = t[k+1] - t[k]
        nv = v + a * dt
        v_pred[k+1] = float(np.clip(nv, 0.0, V_CAP))
    v = v_pred[-1]
    a_pred[-1] = (cP * ap[-1] + cPv * ap[-1] * v + cB * bp[-1] * v
                  + rV * v - kAero * np.sign(v) * v * v + c0)
    out = seg.copy()
    out["v_pred_cl"] = v_pred
    out["a_pred_cl"] = a_pred
    return out


# ---------------- main eval --------------------------------------------

def main(limit_segments: int | None = None, out_dir: Path = Path("out")):
    out_dir = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-02") / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    csvs = find_csvs()
    if limit_segments:
        csvs = csvs[:limit_segments]
    print(f"Found {len(csvs)} segment CSVs")

    # Split: 80/20 by segment so the test set has whole unseen segments.
    rng = np.random.default_rng(42)
    idx = np.arange(len(csvs))
    rng.shuffle(idx)
    n_train = int(0.8 * len(idx))
    train_csvs = [csvs[i] for i in idx[:n_train]]
    test_csvs  = [csvs[i] for i in idx[n_train:]]

    print(f"  train segments: {len(train_csvs)}")
    print(f"  test  segments: {len(test_csvs)}")

    df_train = pd.concat([load_segment(c) for c in train_csvs], ignore_index=True)
    df_train = df_train.dropna(subset=["v_mps", "a_long_mps2", "accel_pedal_pct", "brake_pressed"])
    print(f"  train samples: {len(df_train)}")

    coef = fit(df_train)
    print("\nLearned coefficients (a = cP*ap + cB*bp*v + rV*v + rV2*v^2 + c0):")
    names = ["cP (m/s^2 /%)", "cPv (1/% /s)", "cB (1/s)", "rV (1/s)", "kAero (1/m)", "c0 (m/s^2)"]
    for n, c in zip(names, coef):
        print(f"  {n:18s} = {c:+.5f}")

    # ---- open-loop one-step on TEST ----
    df_test = pd.concat([load_segment(c) for c in test_csvs], ignore_index=True)
    df_test = df_test.dropna(subset=["v_mps", "a_long_mps2", "accel_pedal_pct", "brake_pressed"]).reset_index(drop=True)
    df_test["a_pred_ol"] = predict_a(df_test, coef)
    a_err = df_test["a_pred_ol"] - df_test["a_long_mps2"]
    a_mae  = float(np.mean(np.abs(a_err)))
    a_rmse = float(np.sqrt(np.mean(a_err**2)))
    print(f"\nOpen-loop one-step a prediction on TEST:")
    print(f"  MAE  = {a_mae:.3f} m/s^2")
    print(f"  RMSE = {a_rmse:.3f} m/s^2")

    # ---- closed-loop per segment on TEST ----
    rmse_v_cl  = []   # our model
    rmse_v_imu = []   # baseline 1: integrate sensed IMU a (drift)
    durations  = []
    per_regime_err = {"cruise": [], "accel": [], "brake": [], "coast": [], "stop": []}

    for c in test_csvs:
        seg = load_segment(c)
        seg = seg.dropna(subset=["v_mps", "a_long_mps2", "accel_pedal_pct", "brake_pressed"]).reset_index(drop=True)
        if len(seg) < 50:
            continue
        # closed loop with our model
        seg_cl = closed_loop_segment(seg, coef)
        err = seg_cl["v_pred_cl"] - seg_cl["v_mps"]
        rmse_v_cl.append(float(np.sqrt(np.mean(err**2))))
        durations.append(float(seg["t_s"].iloc[-1] - seg["t_s"].iloc[0]))

        # baseline 1: integrate IMU a_long
        t = seg["t_s"].values
        a_imu = seg["a_long_mps2"].values
        v_imu = np.empty(len(seg))
        v_imu[0] = seg["v_mps"].iloc[0]
        for k in range(len(seg) - 1):
            v_imu[k+1] = max(v_imu[k] + a_imu[k] * (t[k+1] - t[k]), 0.0)
        err_imu = v_imu - seg["v_mps"].values
        rmse_v_imu.append(float(np.sqrt(np.mean(err_imu**2))))

        # per-regime
        regs = regime_labels(seg)
        for r in per_regime_err:
            mask = (regs.values == r)
            if mask.sum() > 5:
                per_regime_err[r].append(float(np.sqrt(np.mean(err.values[mask]**2))))

    print(f"\nClosed-loop integration on TEST ({len(rmse_v_cl)} segments,"
          f" avg duration {np.mean(durations):.1f} s):")
    print(f"  Our model        : v_RMSE = {np.mean(rmse_v_cl):.2f} m/s  (median {np.median(rmse_v_cl):.2f})")
    print(f"  Baseline (∫IMU a): v_RMSE = {np.mean(rmse_v_imu):.2f} m/s  (median {np.median(rmse_v_imu):.2f})")
    print(f"  Baseline (crutch v=v_meas): v_RMSE = 0.00 m/s by construction")

    print("\nPer-regime closed-loop v_RMSE (m/s, mean across test segments):")
    for r, errs in per_regime_err.items():
        if errs:
            print(f"  {r:7s}: {np.mean(errs):.2f}   (n_segments={len(errs)})")
        else:
            print(f"  {r:7s}: n/a")

    # save summary
    summary = {
        "n_train_segments": len(train_csvs),
        "n_test_segments":  len(test_csvs),
        "coef_cP":          float(coef[0]),
        "coef_cPv":         float(coef[1]),
        "coef_cB":          float(coef[2]),
        "coef_rV":          float(coef[3]),
        "coef_kAero":       float(coef[4]),
        "coef_c0":          float(coef[5]),
        "a_mae_test":       a_mae,
        "a_rmse_test":      a_rmse,
        "v_rmse_cl_mean":   float(np.mean(rmse_v_cl)),
        "v_rmse_cl_median": float(np.median(rmse_v_cl)),
        "v_rmse_imu_mean":  float(np.mean(rmse_v_imu)),
        "v_rmse_imu_median":float(np.median(rmse_v_imu)),
        "avg_duration_s":   float(np.mean(durations)),
    }
    for r, errs in per_regime_err.items():
        summary[f"v_rmse_cl_{r}"] = float(np.mean(errs)) if errs else None

    import json
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {out_dir/'summary.json'}")


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit_segments=n)
