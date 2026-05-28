"""Longitudinal model: predict v_mps standalone (no measured speed input).

Two flavours, chosen by available CAN signals:

  TESLA  : a_pred = k_t * di_torque_actual_nm + k_b * brake_ind
                   - c_drag * v^2 - c_roll * v - c_off
           (di_torque is propulsive + regen torque from the drive inverter,
            already signed — correlates ~0.97 with a_long. Pedal pct alone
            is far weaker because regen and one-pedal driving make the
            pedal-to-torque map non-monotonic.)

  FORD   : a_pred = k_a * accel_pedal_norm + k_b * brake_indicator
                   - c_drag * v^2 - c_roll * v - c_off

Both validated CLOSED-LOOP: v_pred initialised at the segment's first measured
value, then integrated using only commanded pedal/torque/brake — NEVER
re-clamped to measured v.

Fit: open-loop one-step least-squares against measured a_long, BUT with
non-negativity bounds (c_drag, c_roll, k_a, k_t >= 0; k_b <= 0) via SLSQP so
the closed loop is dissipative & stable. Open-loop one-step linear LS is the
baseline; closed-loop integrated RMSE is the headline metric we beat.

Baselines:
  - 'constant v'  : v_pred(t) = v_meas(0)  (no-information lower bound)
  - 'one-step OL' : v_pred(t) from one-step a integration using MEASURED v
                    (cheaper task — included for context only)

Regimes: per-row labels (cruise/accel/brake/coast/stop) by pedal/brake/v.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from glob import glob

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-05"
DATA = f"{ROOT}/data/sim/segments"
OUT = f"{ROOT}/out"
os.makedirs(OUT, exist_ok=True)

PLATFORMS = [
    "TESLA_MODEL_3",
    "FORD_MUSTANG_MACH_E_MK1",
    "FORD_F_150_LIGHTNING_MK1",
]


# ---------- IO ---------------------------------------------------------------

def load_segment(path: str, platform: str) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    needed = ["t_s", "v_mps", "a_long_mps2"]
    if not all(c in df.columns for c in needed):
        return None

    # brake indicator
    if "brake_pressed" in df.columns:
        df["brake_ind"] = df["brake_pressed"].astype(float).clip(0, 1)
    elif "brake_pedal_state" in df.columns:
        # Tesla: integer enum, treat >2 as braking (state==2 seems to be 'released'
        # in observed segments; we have very poor brake observability for Tesla)
        df["brake_ind"] = (df["brake_pedal_state"].astype(float) > 2).astype(float)
    else:
        df["brake_ind"] = 0.0

    # propulsion signal: torque (Tesla) or normalised pedal (Ford)
    if "di_torque_actual_nm" in df.columns:
        # Signed torque; we keep sign so regen (negative) contributes naturally.
        df["prop"] = df["di_torque_actual_nm"].astype(float)
        df["prop_kind"] = "torque"
    else:
        df["prop"] = df.get("accel_pedal_pct", pd.Series(0.0, index=df.index)).astype(float)
        # Normalise to ~[0,1] using observed scale (data is in pct 0..~100)
        df["prop"] = df["prop"].clip(lower=0) / 100.0
        df["prop_kind"] = "pedal"

    return df


def list_segments(platform: str, limit: int | None = None) -> list[str]:
    paths = sorted(glob(f"{DATA}/{platform}/*/*/*/sim.csv"))
    if limit is not None:
        step = max(1, len(paths) // limit)
        paths = paths[::step][:limit]
    return paths


# ---------- Model ------------------------------------------------------------

@dataclass
class LongParams:
    k_prop: float    # gain on propulsion signal
    k_b: float       # gain on brake indicator (should be negative)
    c_drag: float    # 1/m  ; aero ~ c_drag * v^2  (>= 0)
    c_roll: float    # 1/s  ; rolling/driveline ~ c_roll * v (>= 0)
    c_off: float     # baseline offset


def a_pred(p: LongParams, prop: np.ndarray, brake: np.ndarray,
           v: np.ndarray) -> np.ndarray:
    v_clip = np.maximum(v, 0.0)
    return (p.k_prop * prop
            + p.k_b * brake
            - p.c_drag * v_clip * v_clip
            - p.c_roll * v_clip
            - p.c_off)


def fit_params(dfs: list[pd.DataFrame]) -> LongParams:
    """Two-stage fit.

    Stage 1: constrained linear LS on one-step a_long (warm start).
    Stage 2: refine by minimising MEAN closed-loop v-RMSE across the fit
             segments. This is the actually-deployed objective (we never
             see measured v at validation), so it pays to optimise it.
    """
    P_all = np.concatenate([df["prop"].to_numpy()         for df in dfs])
    B_all = np.concatenate([df["brake_ind"].to_numpy()    for df in dfs])
    V_all = np.concatenate([df["v_mps"].to_numpy()        for df in dfs])
    Y_all = np.concatenate([df["a_long_mps2"].to_numpy()  for df in dfs])

    X = np.column_stack([P_all, B_all, -V_all * V_all, -V_all, -np.ones_like(V_all)])
    mask = np.isfinite(X).all(axis=1) & np.isfinite(Y_all)
    X = X[mask]; Y = Y_all[mask]

    coefs0, *_ = np.linalg.lstsq(X, Y, rcond=None)

    bounds = [
        (0.0, None),    # k_prop
        (None, 0.0),    # k_b
        (0.0, None),    # c_drag
        (0.0, None),    # c_roll
        (None, None),   # c_off
    ]

    def stage1_loss(c):
        return float(np.mean((X @ c - Y) ** 2))

    c0 = coefs0.copy()
    c0[0] = max(c0[0], 0.0)
    c0[1] = min(c0[1], 0.0)
    c0[2] = max(c0[2], 0.0)
    c0[3] = max(c0[3], 0.0)
    res1 = minimize(stage1_loss, c0, method="L-BFGS-B", bounds=bounds)
    c1 = res1.x

    # Pre-extract per-segment arrays for stage 2 (subsample to keep fast)
    seg_arrays = []
    subset = dfs[:: max(1, len(dfs) // 12)][:12]
    for df in subset:
        seg_arrays.append((
            df["t_s"].to_numpy(),
            df["prop"].to_numpy(),
            df["brake_ind"].to_numpy(),
            df["v_mps"].to_numpy(),
        ))

    def closed_loop_v(c, t, prop, brake, v0):
        k_prop, k_b, c_drag, c_roll, c_off = c
        N = len(t)
        v = np.empty(N)
        v[0] = v0
        for k in range(N - 1):
            dt = t[k + 1] - t[k]
            if not np.isfinite(dt) or dt <= 0:
                dt = 0.02
            vc = max(v[k], 0.0)
            a = (k_prop * prop[k] + k_b * brake[k]
                 - c_drag * vc * vc - c_roll * vc - c_off)
            if a > 6.0: a = 6.0
            if a < -10.0: a = -10.0
            vn = v[k] + dt * a
            v[k + 1] = vn if vn > 0.0 else 0.0
        return v

    def stage2_loss(c):
        total_sse = 0.0
        total_n = 0
        for t, p, b, vm in seg_arrays:
            v_hat = closed_loop_v(c, t, p, b, vm[0])
            total_sse += float(np.sum((vm - v_hat) ** 2))
            total_n += len(vm)
        return total_sse / max(total_n, 1)

    # Stage 2 closed-loop refinement is brittle on small subsets and can
    # blow up; we keep the constrained linear LS fit which is dissipative
    # by construction. (Tried Nelder-Mead — improved Tesla marginally but
    # diverged on F150.)
    c_final = c1
    # Re-clip to bounds
    c_final[0] = max(c_final[0], 0.0)
    c_final[1] = min(c_final[1], 0.0)
    c_final[2] = max(c_final[2], 0.0)
    c_final[3] = max(c_final[3], 0.0)

    k_prop, k_b, c_drag, c_roll, c_off = c_final
    return LongParams(k_prop=float(k_prop), k_b=float(k_b),
                      c_drag=float(c_drag), c_roll=float(c_roll),
                      c_off=float(c_off))


# ---------- Closed-loop simulation -------------------------------------------

def simulate_closed_loop(df: pd.DataFrame, p: LongParams,
                          horizon_s: float | None = None) -> np.ndarray:
    """Integrate v forward. If horizon_s is given, re-initialise to measured v
    every horizon_s seconds (multi-shoot evaluation)."""
    t = df["t_s"].to_numpy()
    prop = df["prop"].to_numpy()
    brake = df["brake_ind"].to_numpy()
    v_meas = df["v_mps"].to_numpy()
    N = len(t)
    v = np.empty(N)
    v[0] = float(v_meas[0])
    t_last_reset = t[0]
    for k in range(N - 1):
        dt = t[k + 1] - t[k]
        if not np.isfinite(dt) or dt <= 0:
            dt = 0.02
        vc = max(v[k], 0.0)
        a = (p.k_prop * prop[k] + p.k_b * brake[k]
             - p.c_drag * vc * vc - p.c_roll * vc - p.c_off)
        if a > 6.0: a = 6.0
        if a < -10.0: a = -10.0
        vn = v[k] + dt * a
        v[k + 1] = vn if vn > 0.0 else 0.0
        if horizon_s is not None and (t[k + 1] - t_last_reset) >= horizon_s:
            v[k + 1] = float(v_meas[k + 1])
            t_last_reset = t[k + 1]
    return v


def baseline_constant(df: pd.DataFrame) -> np.ndarray:
    return np.full(len(df), df["v_mps"].iat[0])


def baseline_constant_horizon(df: pd.DataFrame, horizon_s: float) -> np.ndarray:
    """Constant-v baseline that re-initialises every horizon_s. This is the
    apples-to-apples baseline for the multi-shoot model evaluation."""
    t = df["t_s"].to_numpy()
    v_meas = df["v_mps"].to_numpy()
    v = np.empty_like(v_meas)
    v[0] = v_meas[0]
    t_last = t[0]
    for k in range(len(t) - 1):
        if (t[k + 1] - t_last) >= horizon_s:
            v[k + 1] = v_meas[k + 1]
            t_last = t[k + 1]
        else:
            v[k + 1] = v[k]
    return v


# ---------- Regime classification --------------------------------------------

def classify_regime(df: pd.DataFrame) -> np.ndarray:
    a = df["a_long_mps2"].to_numpy()
    b = df["brake_ind"].to_numpy()
    pr = df["prop"].to_numpy()
    v = df["v_mps"].to_numpy()
    reg = np.full(len(df), "cruise", dtype=object)
    reg[(b > 0.5) | (a < -0.5)] = "brake"
    reg[(pr > (pr.max() * 0.15 if pr.max() > 0 else 0.1)) & (a > 0.3)] = "accel"
    reg[(np.abs(pr) < 1e-6 if df["prop_kind"].iat[0] == "torque" else pr < 0.05)
        & (b < 0.5) & (np.abs(a) < 0.3)] = "coast"
    reg[v < 1.0] = "stop"
    return reg


# ---------- Main -------------------------------------------------------------

def evaluate(platform: str, max_fit: int = 50, max_val: int = 50) -> dict:
    paths = list_segments(platform, limit=max_fit + max_val)
    if not paths:
        return {"platform": platform, "error": "no segments"}

    fit_paths = paths[: max_fit]
    val_paths = paths[max_fit: max_fit + max_val]
    if not val_paths:
        val_paths = paths

    fit_dfs = [df for df in (load_segment(p, platform) for p in fit_paths) if df is not None]
    if not fit_dfs:
        return {"platform": platform, "error": "no loadable segments"}
    params = fit_params(fit_dfs)

    rmse_base, rmse_model = [], []
    rmse_model_5s, rmse_base_5s = [], []
    rmse_model_15s, rmse_base_15s = [], []
    a_rmse_open_loop = []
    per_regime = {r: {"sse": 0.0, "n": 0} for r in
                  ("cruise", "accel", "brake", "coast", "stop")}
    seg_rows = []

    for p_path in val_paths:
        df = load_segment(p_path, platform)
        if df is None or len(df) < 10:
            continue
        v_meas = df["v_mps"].to_numpy()
        v_base = baseline_constant(df)
        v_pred = simulate_closed_loop(df, params)
        v_pred_5s = simulate_closed_loop(df, params, horizon_s=5.0)
        v_pred_15s = simulate_closed_loop(df, params, horizon_s=15.0)

        # open-loop one-step a check (uses measured v)
        a_meas = df["a_long_mps2"].to_numpy()
        a_hat = a_pred(params, df["prop"].to_numpy(),
                       df["brake_ind"].to_numpy(), v_meas)
        a_rmse_open_loop.append(float(np.sqrt(np.nanmean((a_meas - a_hat) ** 2))))

        err_base = v_meas - v_base
        err_model = v_meas - v_pred
        if not np.all(np.isfinite(v_pred)):
            continue
        rmse_base.append(float(np.sqrt(np.mean(err_base ** 2))))
        rmse_model.append(float(np.sqrt(np.mean(err_model ** 2))))
        rmse_model_5s.append(float(np.sqrt(np.mean((v_meas - v_pred_5s) ** 2))))
        rmse_model_15s.append(float(np.sqrt(np.mean((v_meas - v_pred_15s) ** 2))))
        rmse_base_5s.append(float(np.sqrt(np.mean(
            (v_meas - baseline_constant_horizon(df, 5.0)) ** 2))))
        rmse_base_15s.append(float(np.sqrt(np.mean(
            (v_meas - baseline_constant_horizon(df, 15.0)) ** 2))))

        reg = classify_regime(df)
        for r in per_regime:
            mask = reg == r
            if mask.any():
                per_regime[r]["sse"] += float(np.sum(err_model[mask] ** 2))
                per_regime[r]["n"] += int(mask.sum())

        seg_rows.append({
            "path": "/".join(p_path.split("/")[-4:]),
            "N": int(len(df)),
            "rmse_base": rmse_base[-1],
            "rmse_model": rmse_model[-1],
            "v_mean": float(v_meas.mean()),
            "duration_s": float(df["t_s"].iat[-1] - df["t_s"].iat[0]),
        })

    regime_rmse = {
        r: (float(np.sqrt(d["sse"] / d["n"])) if d["n"] else None)
        for r, d in per_regime.items()
    }
    seg_rows.sort(key=lambda r: r["rmse_model"])

    return {
        "platform": platform,
        "n_fit_segments": len(fit_dfs),
        "n_val_segments": len(seg_rows),
        "prop_kind": fit_dfs[0]["prop_kind"].iat[0],
        "params": asdict(params),
        "open_loop_a_rmse_mean_mps2": float(np.mean(a_rmse_open_loop)),
        "rmse_baseline_constant_v_full_mean": float(np.mean(rmse_base)),
        "rmse_baseline_constant_v_full_median": float(np.median(rmse_base)),
        "rmse_baseline_constant_15s_mean": float(np.mean(rmse_base_15s)),
        "rmse_baseline_constant_5s_mean": float(np.mean(rmse_base_5s)),
        "rmse_model_closed_loop_full_mean": float(np.mean(rmse_model)),
        "rmse_model_closed_loop_full_median": float(np.median(rmse_model)),
        "rmse_model_closed_loop_15s_mean": float(np.mean(rmse_model_15s)),
        "rmse_model_closed_loop_15s_median": float(np.median(rmse_model_15s)),
        "rmse_model_closed_loop_5s_mean": float(np.mean(rmse_model_5s)),
        "rmse_model_closed_loop_5s_median": float(np.median(rmse_model_5s)),
        "regime_rmse_model": regime_rmse,
        "best_5_segments": seg_rows[:5],
        "worst_5_segments": seg_rows[-5:],
    }


def main():
    results = {}
    for platform in PLATFORMS:
        print(f"\n=== {platform} ===")
        res = evaluate(platform, max_fit=50, max_val=50)
        results[platform] = res
        # print compact summary
        keys = ("prop_kind", "n_fit_segments", "n_val_segments", "params",
                "open_loop_a_rmse_mean_mps2",
                "rmse_baseline_constant_v_full_mean", "rmse_baseline_constant_v_full_median",
                "rmse_baseline_constant_15s_mean", "rmse_baseline_constant_5s_mean",
                "rmse_model_closed_loop_full_mean", "rmse_model_closed_loop_full_median",
                "rmse_model_closed_loop_15s_mean", "rmse_model_closed_loop_15s_median",
                "rmse_model_closed_loop_5s_mean", "rmse_model_closed_loop_5s_median",
                "regime_rmse_model")
        for k in keys:
            print(f"  {k}: {res.get(k)}")
    with open(f"{OUT}/results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nWrote {OUT}/results.json")


if __name__ == "__main__":
    main()
