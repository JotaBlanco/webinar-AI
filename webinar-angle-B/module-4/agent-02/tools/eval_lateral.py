"""Lateral-fidelity variant evaluator for Ford Mach-E MK1.

Runs a locked variant ladder against the pre-computed `yaw_rate_resid_rads`
in the Ford sim CSVs and reports overall + per-regime RMSE plus marginal
drops in strict V0 -> V_last order.

Variants:
  V0 baseline                   : yaw_rate_resid_rads as-is (no preprocessing)
  V1 per-segment bias removed   : subtract per-segment mean residual on
                                  *straight-line* samples (soaks IMU yaw-gyro
                                  offset and any constant calibration bias)
  V2 linear-ST gain (prior Cα)  : replace KS yaw-rate prediction with steady-
                                  state linear single-track gain using the
                                  openpilot-canonical cornering stiffnesses
                                  from PARAM_BY_PLATFORM. Includes V1 bias.
  V3 linear-ST, fit Cα          : refit (C_αf, C_αr) jointly via OLS on the
                                  steady-cornering subset (bounded to 50-500
                                  kN/rad). Includes V1 bias.

Same segment set + same regime mask across every variant.
"""

import glob
import json
import os
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(MOD, "code"))

# Mach-E parameters (from PARAM_BY_PLATFORM, restated in skill).
L = 2.984
M = 2336.0
LF = 1.313
LR = 1.671
CAF_PRIOR = 286_551.0
CAR_PRIOR = 355_912.0

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
DATA_DIR = os.path.join(MOD, "data", "sim", "segments", PLATFORM)

# Regime thresholds.
DELTA_CORN = 0.01          # |delta_road| boundary for straight vs cornering
DDDT_TRANS = 0.05          # |d delta / dt| boundary steady vs transient
V_MIN = 2.0                # ST gain falls back to KS below this speed


def load_segments():
    paths = sorted(glob.glob(os.path.join(DATA_DIR, "*", "*", "*", "sim.csv")))
    frames = []
    for i, p in enumerate(paths):
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        needed = {"t_s", "delta_road_rad", "v_mps", "yaw_rate_meas_rads",
                  "yaw_rate_pred_rads", "yaw_rate_resid_rads"}
        if not needed.issubset(df.columns):
            continue
        df = df.copy()
        df["seg_id"] = i
        frames.append(df)
    if not frames:
        raise SystemExit("No segments found")
    return pd.concat(frames, ignore_index=True)


def regime_masks(df: pd.DataFrame):
    delta = df["delta_road_rad"].to_numpy()
    # finite difference on per-segment time grid (dt = 0.02s by contract)
    ddelta_dt = np.zeros_like(delta)
    for sid, idx in df.groupby("seg_id").groups.items():
        idx = np.asarray(idx)
        d = delta[idx]
        ddelta_dt[idx] = np.gradient(d, 0.02)
    cornering = np.abs(delta) >= DELTA_CORN
    straight = ~cornering
    transient = cornering & (np.abs(ddelta_dt) >= DDDT_TRANS)
    steady = cornering & ~transient
    return {"straight": straight, "steady": steady, "transient": transient,
            "all": np.ones_like(straight, dtype=bool)}, ddelta_dt


def rmse(x: np.ndarray, mask: np.ndarray) -> float:
    sel = x[mask]
    sel = sel[np.isfinite(sel)]
    if sel.size == 0:
        return float("nan")
    return float(np.sqrt(np.mean(sel ** 2)))


def st_yaw_pred(v: np.ndarray, delta: np.ndarray, caf: float, car: float) -> np.ndarray:
    """Linear ST steady-state gain. Falls back to KS for v < V_MIN."""
    K_us = M * (LR * car - LF * caf) / (L ** 2 * caf * car)
    denom = 1.0 + K_us * v ** 2
    psidot = v * delta / (L * denom)
    # KS fallback for low speed
    ks = (v / L) * np.tan(delta)
    return np.where(v < V_MIN, ks, psidot)


def fit_st_caf_car(df, mask_steady):
    """Fit (C_αf, C_αr) on steady-cornering samples minimising residual RMSE.

    Bounded to 50-500 kN/rad each. Pegging is reported as a regression flag.
    """
    v = df["v_mps"].to_numpy()[mask_steady]
    d = df["delta_road_rad"].to_numpy()[mask_steady]
    y = df["yaw_rate_meas_rads"].to_numpy()[mask_steady]

    # Scale parameters to O(1) for the optimizer.
    SCALE = 1e5

    def loss(theta_scaled):
        caf, car = theta_scaled[0] * SCALE, theta_scaled[1] * SCALE
        pred = st_yaw_pred(v, d, caf, car)
        r = pred - y
        return float(np.mean(r ** 2))

    best = None
    for x0 in [(CAF_PRIOR / SCALE, CAR_PRIOR / SCALE),
               (1.5, 2.0), (4.0, 4.0), (1.0, 5.0), (3.0, 3.0)]:
        res = minimize(loss, x0=x0, method="L-BFGS-B",
                       bounds=[(0.5, 5.0), (0.5, 5.0)],
                       options={"ftol": 1e-12, "gtol": 1e-10})
        if best is None or res.fun < best.fun:
            best = res
    return float(best.x[0] * SCALE), float(best.x[1] * SCALE), best


def main():
    df = load_segments()
    n_segs = df["seg_id"].nunique()
    n_samp = len(df)
    print(f"platform={PLATFORM} segments={n_segs} samples={n_samp}")

    masks, ddelta_dt = regime_masks(df)

    # Sign sanity on cornering samples.
    corn = masks["steady"] | masks["transient"]
    sign_corr = float(np.corrcoef(
        df["delta_road_rad"].to_numpy()[corn],
        df["yaw_rate_meas_rads"].to_numpy()[corn])[0, 1])
    print(f"sign_check corr(delta_road, yaw_rate_meas) on cornering = {sign_corr:+.3f}")

    # V0 — as-is residual
    r0 = df["yaw_rate_resid_rads"].to_numpy()

    # V1 — per-segment bias on straights only
    bias_by_seg = {}
    v1_bias = np.zeros(len(df))
    for sid, idx in df.groupby("seg_id").groups.items():
        idx = np.asarray(idx)
        straight_in_seg = masks["straight"][idx]
        if straight_in_seg.sum() < 10:
            b = 0.0
        else:
            b = float(np.nanmean(r0[idx][straight_in_seg]))
        bias_by_seg[int(sid)] = b
        v1_bias[idx] = b
    r1 = r0 - v1_bias
    df["v1_bias"] = v1_bias

    # V2 — linear-ST prior Cα. Recompute yaw_rate_pred, then refit per-segment
    # bias on straights (V1 carry-over, but estimated against the ST predictor
    # — not against KS residual — so we don't double-count KS-specific bias).
    v = df["v_mps"].to_numpy()
    d = df["delta_road_rad"].to_numpy()
    y = df["yaw_rate_meas_rads"].to_numpy()
    pred_v2 = st_yaw_pred(v, d, CAF_PRIOR, CAR_PRIOR)
    raw_resid_v2 = pred_v2 - y
    bias_v2 = np.zeros_like(raw_resid_v2)
    for sid, idx in df.groupby("seg_id").groups.items():
        idx = np.asarray(idx)
        s = masks["straight"][idx]
        bias_v2[idx] = float(np.nanmean(raw_resid_v2[idx][s])) if s.sum() >= 10 else 0.0
    r2 = raw_resid_v2 - bias_v2

    # V3 — fit Cα on steady cornering against meas (without V1 bias mismatch).
    caf_fit, car_fit, opt = fit_st_caf_car(df, masks["steady"])
    pegged = (
        abs(caf_fit - 500_000) < 1.0 or abs(caf_fit - 50_000) < 1.0 or
        abs(car_fit - 500_000) < 1.0 or abs(car_fit - 50_000) < 1.0
    )
    pred_v3 = st_yaw_pred(v, d, caf_fit, car_fit)
    raw_resid_v3 = pred_v3 - y
    bias_v3 = np.zeros_like(raw_resid_v3)
    for sid, idx in df.groupby("seg_id").groups.items():
        idx = np.asarray(idx)
        s = masks["straight"][idx]
        bias_v3[idx] = float(np.nanmean(raw_resid_v3[idx][s])) if s.sum() >= 10 else 0.0
    r3 = raw_resid_v3 - bias_v3

    variants = {"V0_baseline": r0, "V1_seg_bias": r1,
                "V2_ST_prior": r2, "V3_ST_fit": r3}

    out = {
        "platform": PLATFORM,
        "n_segments": n_segs,
        "n_samples": int(n_samp),
        "sign_check_corr": sign_corr,
        "regime_counts": {k: int(v.sum()) for k, v in masks.items()},
        "variants": {},
        "v2_params": {"C_af": CAF_PRIOR, "C_ar": CAR_PRIOR},
        "v3_params": {"C_af": caf_fit, "C_ar": car_fit, "pegged": pegged,
                      "opt_success": bool(opt.success)},
    }

    print()
    print(f"{'variant':<18} {'all':>8} {'straight':>10} {'steady':>10} {'transient':>11}")
    prev_all = None
    for name, r in variants.items():
        rmses = {k: rmse(r, m) for k, m in masks.items()}
        out["variants"][name] = rmses
        line = f"{name:<18} {rmses['all']:>8.5f} {rmses['straight']:>10.5f} {rmses['steady']:>10.5f} {rmses['transient']:>11.5f}"
        if prev_all is not None:
            drop = prev_all - rmses['all']
            line += f"   marginal_drop_all={drop:+.5f}"
        prev_all = rmses['all']
        print(line)

    total_drop = variants["V0_baseline"]
    # accounting: strict marginal in fixed ladder order, all-regime RMSE
    rmse_seq = [rmse(variants[n], masks["all"]) for n in variants]
    marginals = [rmse_seq[i - 1] - rmse_seq[i] for i in range(1, len(rmse_seq))]
    total = rmse_seq[0] - rmse_seq[-1]
    sum_marg = sum(marginals)
    out["accounting"] = {
        "rmse_sequence_all": rmse_seq,
        "marginal_drops_all": marginals,
        "total_drop": total,
        "sum_of_marginals": sum_marg,
        "within_15pct": abs(sum_marg - total) <= 0.15 * abs(total) if total else True,
    }

    out_dir = os.path.join(MOD, "out")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "lateral_eval.json"), "w") as f:
        json.dump(out, f, indent=2)
    print()
    print(f"wrote {os.path.join(out_dir, 'lateral_eval.json')}")
    print(f"V3 Cα: C_af={caf_fit:.0f} N/rad  C_ar={car_fit:.0f} N/rad  pegged={pegged}")


if __name__ == "__main__":
    main()
