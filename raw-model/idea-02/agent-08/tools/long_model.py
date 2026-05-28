"""Longitudinal model for Tesla Model 3 — predicts v_mps from drive-inverter
torque (commanded by powertrain controller, NOT measured speed).

Form:
    m_eff * dv/dt = k_T * T_motor - F_roll - F_aero(v) - F_brake
    F_aero(v)   = 0.5 * rho * Cd * A * v^2  ->  c2 * v^2
    F_roll      = c0 (constant rolling resistance + small grade bias)
    F_brake     ~ k_B * brake_torque (Tesla brake_pedal_state is degenerate -> 0)

Free parameters fit by ridge regression on the linear-in-coeffs form:
    a_meas ~ beta_T * T_motor + beta_v2 * v^2 + beta_0
with beta_T = k_T / m_eff, beta_v2 = -c2/m_eff, beta_0 = -c0/m_eff.

Once fit, integrate dv/dt forward in closed loop using ONLY:
  - T_motor(t)   (commanded torque, sensed from inverter)
  - v(0)         (initial speed)

Compare predicted v(t) against measured v(t) (v_mps).
"""

import argparse
import glob
import json
import os

import numpy as np
import pandas as pd


PLATFORM = "TESLA_MODEL_3"
DATA_DIR = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-08/data/sim/segments"
OUT_DIR = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-08/out"


def load_segments(platform: str, limit: int | None = None) -> list[tuple[str, pd.DataFrame]]:
    pat = os.path.join(DATA_DIR, platform, "*", "*", "*", "sim.csv")
    paths = sorted(glob.glob(pat))
    if limit:
        paths = paths[:limit]
    segs = []
    for p in paths:
        try:
            df = pd.read_csv(p)
            if "v_mps" not in df or "di_torque_actual_nm" not in df or "a_long_mps2" not in df:
                continue
            if len(df) < 200:
                continue
            segs.append((p, df))
        except Exception:
            continue
    return segs


def _features(v: np.ndarray, T: np.ndarray) -> np.ndarray:
    """Feature matrix for the longitudinal acceleration model.

    Columns:
      0: T+ (positive part of motor torque)      -> drive
      1: T- (negative part of motor torque)      -> regen
      2: v^2                                      -> aero drag
      3: v                                        -> linear bearing/friction
      4: 1                                        -> rolling resistance + bias
    """
    T_pos = np.maximum(T, 0.0)
    T_neg = np.minimum(T, 0.0)
    return np.column_stack([T_pos, T_neg, v * v, v, np.ones_like(v)])


def fit_global(segs: list[tuple[str, pd.DataFrame]]):
    """Ridge fit of a ~ features(v, T) @ beta across all segments."""
    Xs, ys = [], []
    for _, df in segs:
        v = df.v_mps.values
        T = df.di_torque_actual_nm.values
        a = df.a_long_mps2.values
        m = np.isfinite(v) & np.isfinite(T) & np.isfinite(a) & (v > 0.5)
        Xs.append(_features(v[m], T[m]))
        ys.append(a[m])
    X = np.vstack(Xs)
    y = np.concatenate(ys)
    lam = 1e-4
    A = X.T @ X + lam * np.eye(X.shape[1])
    b = X.T @ y
    beta = np.linalg.solve(A, b)
    return beta


def predict_a(v: float, T: float, beta) -> float:
    T_pos = max(T, 0.0)
    T_neg = min(T, 0.0)
    return beta[0] * T_pos + beta[1] * T_neg + beta[2] * v * v + beta[3] * v + beta[4]


def simulate_v(df: pd.DataFrame, beta) -> np.ndarray:
    t = df.t_s.values
    T = df.di_torque_actual_nm.values
    v0 = float(df.v_mps.values[0])
    v_pred = np.zeros(len(t))
    v_pred[0] = v0
    for k in range(len(t) - 1):
        dt = t[k + 1] - t[k]
        # RK4 in v alone (a depends on v and T at the timestep — hold T zero-order)
        T_k = T[k]
        a1 = predict_a(v_pred[k], T_k, beta)
        a2 = predict_a(v_pred[k] + 0.5 * dt * a1, T_k, beta)
        a3 = predict_a(v_pred[k] + 0.5 * dt * a2, T_k, beta)
        a4 = predict_a(v_pred[k] + dt * a3, T_k, beta)
        v_pred[k + 1] = v_pred[k] + (dt / 6.0) * (a1 + 2 * a2 + 2 * a3 + a4)
        # Speed can't go negative physically
        if v_pred[k + 1] < 0:
            v_pred[k + 1] = 0.0
    return v_pred


def regime_label(row) -> str:
    a = row.a_long_mps2
    v = row.v_mps
    if v < 1.0:
        return "stopped"
    if a > 0.3:
        return "accel"
    if a < -0.3:
        return "brake"
    return "cruise"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit-segs", type=int, default=20, help="num segments for fit")
    ap.add_argument("--eval-segs", type=int, default=30, help="num segments for eval")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    all_segs = load_segments(PLATFORM, limit=args.fit_segs + args.eval_segs)
    if len(all_segs) < args.fit_segs + 1:
        print(f"Only got {len(all_segs)} segments")
        return

    fit_segs = all_segs[: args.fit_segs]
    eval_segs = all_segs[args.fit_segs : args.fit_segs + args.eval_segs]

    beta = fit_global(fit_segs)
    print("Fitted coefficients (a = T+*b0 + T-*b1 + v^2*b2 + v*b3 + b4):")
    print(f"  beta_Tpos = {beta[0]:.6e}")
    print(f"  beta_Tneg = {beta[1]:.6e}")
    print(f"  beta_v2   = {beta[2]:.6e}")
    print(f"  beta_v    = {beta[3]:.6e}")
    print(f"  beta_0    = {beta[4]:.6e}")
    m_assumed = 2035.0
    print(f"  implied drive k+ (N/Nm)  = {beta[0] * m_assumed:.4f}")
    print(f"  implied regen k- (N/Nm)  = {beta[1] * m_assumed:.4f}")
    print(f"  implied aero c2  (N/(m/s)^2) = {-beta[2] * m_assumed:.4f}")
    print(f"  implied bearing c1 (N/(m/s)) = {-beta[3] * m_assumed:.4f}")
    print(f"  implied rolling c0 (N)       = {-beta[4] * m_assumed:.4f}")

    # Baselines
    # Baseline 1: predict v(t) = v(0) (no model)
    # Baseline 2: predict v(t) = mean(v) for the whole segment
    # Final: closed-loop integration

    results = []
    for path, df in eval_segs:
        v_meas = df.v_mps.values
        v_pred = simulate_v(df, beta)
        # baseline: hold initial speed
        v_b_hold = np.full_like(v_meas, v_meas[0])
        # baseline: integrate a_long IMU forward (this IS using IMU, not predicting from cmds)
        # skip — that's basically a different crutch
        rmse_pred = float(np.sqrt(np.mean((v_pred - v_meas) ** 2)))
        rmse_hold = float(np.sqrt(np.mean((v_b_hold - v_meas) ** 2)))
        mae_pred = float(np.mean(np.abs(v_pred - v_meas)))
        mae_hold = float(np.mean(np.abs(v_b_hold - v_meas)))
        # one-step open-loop a prediction error
        a_meas = df.a_long_mps2.values
        Xfeat = _features(df.v_mps.values, df.di_torque_actual_nm.values)
        a_pred = Xfeat @ beta
        rmse_a = float(np.sqrt(np.mean((a_pred - a_meas) ** 2)))

        # Per-regime breakdown
        df2 = df.copy()
        df2["regime"] = df2.apply(regime_label, axis=1)
        regime_rmse = {}
        for reg in ("cruise", "accel", "brake", "stopped"):
            mask = (df2.regime == reg).values
            if mask.sum() > 5:
                regime_rmse[reg] = float(np.sqrt(np.mean((v_pred[mask] - v_meas[mask]) ** 2)))
            else:
                regime_rmse[reg] = None

        results.append({
            "path": path.split("data/sim/")[-1],
            "rows": len(df),
            "duration_s": float(df.t_s.values[-1]),
            "v_mean": float(v_meas.mean()),
            "v_range": [float(v_meas.min()), float(v_meas.max())],
            "rmse_v_closed_loop": rmse_pred,
            "rmse_v_baseline_hold_v0": rmse_hold,
            "mae_v_closed_loop": mae_pred,
            "mae_v_baseline_hold_v0": mae_hold,
            "rmse_a_one_step": rmse_a,
            "regime_rmse_v": regime_rmse,
        })

    # Aggregate
    agg = {
        "n_eval_segments": len(results),
        "rmse_v_closed_loop_median": float(np.median([r["rmse_v_closed_loop"] for r in results])),
        "rmse_v_closed_loop_mean": float(np.mean([r["rmse_v_closed_loop"] for r in results])),
        "rmse_v_baseline_hold_v0_median": float(np.median([r["rmse_v_baseline_hold_v0"] for r in results])),
        "rmse_v_baseline_hold_v0_mean": float(np.mean([r["rmse_v_baseline_hold_v0"] for r in results])),
        "rmse_a_one_step_median": float(np.median([r["rmse_a_one_step"] for r in results])),
        "mae_v_closed_loop_median": float(np.median([r["mae_v_closed_loop"] for r in results])),
    }
    # regime aggregates
    for reg in ("cruise", "accel", "brake", "stopped"):
        vals = [r["regime_rmse_v"][reg] for r in results if r["regime_rmse_v"][reg] is not None]
        if vals:
            agg[f"rmse_v_regime_{reg}_median"] = float(np.median(vals))
            agg[f"n_segments_with_{reg}"] = len(vals)

    print("\n=== Aggregate ===")
    for k, v in agg.items():
        print(f"  {k}: {v}")

    out = {
        "platform": PLATFORM,
        "n_fit_segments": args.fit_segs,
        "coefficients": {"beta_T": float(beta[0]), "beta_v2": float(beta[1]), "beta_0": float(beta[2])},
        "aggregate": agg,
        "per_segment": results,
    }
    out_path = os.path.join(OUT_DIR, "long_model_results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
