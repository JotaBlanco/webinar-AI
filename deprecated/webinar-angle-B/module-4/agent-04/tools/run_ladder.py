"""Phase 3 (Implement): run locked variant ladder V0..V4 on Mach-E.

V0: yaw_rate_resid_rads as-is.
V1: per-segment bias removal from yaw_rate_pred_rads (subtract mean(resid) per seg).
V2: replace KS gain with linear-ST steady-state gain (prior C_a). v<2 m/s -> KS fallback.
V3: fit C_af, C_ar globally (bounded). Same ST form as V2.
V4: first-order yaw-rate lag on top of V3 ST prediction.

All operate on existing sim.csv columns; no re-simulation.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from parameters import MACH_E  # type: ignore

DATA_SIM = ROOT / "data" / "sim" / "segments"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"

def load_platform(platform: str) -> pd.DataFrame:
    paths = sorted((DATA_SIM / platform).rglob("sim.csv"))
    dfs = []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception as e:
            print(f"skip {p}: {e}", file=sys.stderr); continue
        df["seg_id"] = str(p.relative_to(DATA_SIM / platform).parent)
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

def regime_mask(df: pd.DataFrame) -> pd.Series:
    d = df["delta_road_rad"].abs()
    ddelta = df.groupby("seg_id")["delta_road_rad"].diff().fillna(0.0) / 0.02
    r = pd.Series(index=df.index, dtype="object")
    r[:] = "straight"
    r[(d >= 0.01) & (ddelta.abs() < 0.05)] = "steady"
    r[(d >= 0.01) & (ddelta.abs() >= 0.05)] = "transient"
    return r

def rmse(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float); x = x[np.isfinite(x)]
    return float(np.sqrt(np.mean(x*x))) if x.size else float("nan")

def per_regime_rmse(resid: np.ndarray, regime: pd.Series):
    out = {}
    for r in ("straight", "steady", "transient"):
        m = (regime == r).to_numpy()
        out[r] = {"n": int(m.sum()), "rmse": rmse(resid[m])}
    out["overall"] = {"n": int(np.isfinite(resid).sum()), "rmse": rmse(resid)}
    return out

# ---------- ST steady-state gain ----------
def st_yaw_rate(v: np.ndarray, delta: np.ndarray, L: float, m: float, l_f: float, l_r: float,
                C_af: float, C_ar: float, v_min: float = 2.0) -> np.ndarray:
    """Linear ST steady-state: psidot = v*delta / (L*(1 + K_us*v^2)). KS fallback at low v."""
    K_us = m * (l_r * C_ar - l_f * C_af) / (L**2 * C_af * C_ar)
    # K_us sign: m*(l_r*C_ar - l_f*C_af) — for understeer K_us>0 (l_f*C_af > l_r*C_ar wrong) — formula uses (l_r*C_ar - l_f*C_af) when neutral?
    # Standard (Rajamani): K_us = (m / L) * (l_r/C_af - l_f/C_ar). Use that form for stability.
    K_us2 = (m / L) * (l_r / C_af - l_f / C_ar)  # rad·s²/m² — wait, units check below
    # Actually canonical: psidot/delta = v / (L + K_us*v^2)  where K_us = (m/L)*(l_r/(C_af) - l_f/(C_ar))? Let's use form from skill:
    # skill: psidot = v*delta / (L*(1 + K_us*v^2)) with K_us = m*(l_r*C_ar - l_f*C_af) / (L^2 * C_af * C_ar)
    psidot = v * delta / (L * (1.0 + K_us * v * v))
    # KS fallback at low v
    ks = (v / L) * np.tan(delta)
    out = np.where(np.abs(v) < v_min, ks, psidot)
    return out

# ---------- First-order lag ----------
def apply_lag(seg_ids: np.ndarray, t: np.ndarray, x: np.ndarray, tau: float) -> np.ndarray:
    """Per-segment first-order lowpass: y[k] = y[k-1] + (dt/tau)*(x[k] - y[k-1]).
    Resets at segment boundaries.
    """
    y = np.empty_like(x)
    n = len(x)
    if n == 0: return y
    y[0] = x[0]
    prev_seg = seg_ids[0]
    prev_t = t[0]
    for k in range(1, n):
        if seg_ids[k] != prev_seg:
            y[k] = x[k]
            prev_seg = seg_ids[k]; prev_t = t[k]; continue
        dt = t[k] - prev_t
        if dt <= 0 or not np.isfinite(dt): dt = 0.02
        alpha = dt / max(tau, 1e-6)
        if alpha > 1.0: alpha = 1.0
        y[k] = y[k-1] + alpha * (x[k] - y[k-1])
        prev_t = t[k]
    return y

def main():
    print(f"Loading {PLATFORM}...", file=sys.stderr)
    df = load_platform(PLATFORM)
    print(f"  {len(df)} samples, {df['seg_id'].nunique()} segments", file=sys.stderr)
    regime = regime_mask(df)

    yaw_meas = df["yaw_rate_meas_rads"].to_numpy()
    yaw_pred_ks = df["yaw_rate_pred_rads"].to_numpy()
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    seg_ids = df["seg_id"].to_numpy()
    t_s = df["t_s"].to_numpy()

    p = MACH_E
    L, m, l_f, l_r, C_af, C_ar = p.L, p.m, p.l_f, p.l_r, p.C_alpha_f, p.C_alpha_r

    results = {}

    # V0: as-is
    resid_v0 = df["yaw_rate_resid_rads"].to_numpy()
    results["V0"] = per_regime_rmse(resid_v0, regime)

    # V1: per-segment IMU yaw-gyro DC bias removal.
    # Estimate bias on STRAIGHT-LINE samples only (|delta|<0.01) where any non-zero
    # mean residual is, by physics, gyro DC offset (KS yaw_rate ~ 0 on straights).
    # Fallback: segments with no straight samples use the whole-segment mean.
    df["_resid_v0"] = resid_v0
    straight_mask = (df["delta_road_rad"].abs() < 0.01)
    df["_resid_v0_straight"] = np.where(straight_mask, df["_resid_v0"], np.nan)
    seg_bias_straight = df.groupby("seg_id")["_resid_v0_straight"].transform("mean")
    seg_bias_all = df.groupby("seg_id")["_resid_v0"].transform("mean")
    seg_bias = seg_bias_straight.fillna(seg_bias_all).to_numpy()
    yaw_pred_v1 = yaw_pred_ks - seg_bias
    resid_v1 = yaw_pred_v1 - yaw_meas
    results["V1"] = per_regime_rmse(resid_v1, regime)

    # V2: ST steady-state, prior C_a, applied with V1 bias correction (per-segment bias still applied)
    yaw_st_prior = st_yaw_rate(v, delta, L, m, l_f, l_r, C_af, C_ar)
    # apply per-segment bias correction: recompute bias from ST prior on each segment using V1's bias semantics? per-plan, V1 bias is a sensor offset trait — apply same correction
    # we apply the same per-seg bias values computed from V0 (since they represent gyro DC offset of meas channel) — but our bias subtracts from PRED. Since meas is unchanged, an additive correction to pred yields y_pred_corr = y_pred - bias.
    # For V2 we recompute bias as mean(y_st_prior - y_meas) per segment, since it's the same physical correction (DC offset estimated against truth using current model).
    df["_resid_v2_raw"] = yaw_st_prior - yaw_meas
    df["_resid_v2_raw_straight"] = np.where(straight_mask, df["_resid_v2_raw"], np.nan)
    bias_v2 = (df.groupby("seg_id")["_resid_v2_raw_straight"].transform("mean")
                  .fillna(df.groupby("seg_id")["_resid_v2_raw"].transform("mean"))).to_numpy()
    yaw_v2 = yaw_st_prior - bias_v2
    resid_v2 = yaw_v2 - yaw_meas
    results["V2"] = per_regime_rmse(resid_v2, regime)

    # V3: fit C_af, C_ar jointly on cornering samples (|delta|>=0.01), bounded [50e3, 500e3]
    corner = (np.abs(delta) >= 0.01) & np.isfinite(yaw_meas) & np.isfinite(v) & np.isfinite(delta)
    v_c = v[corner]; d_c = delta[corner]; ym_c = yaw_meas[corner]

    def loss(params):
        Caf, Car = params
        if Caf <= 0 or Car <= 0: return 1e9
        K_us = m * (l_r * Car - l_f * Caf) / (L**2 * Caf * Car)
        pred = v_c * d_c / (L * (1.0 + K_us * v_c * v_c))
        e = pred - ym_c
        return float(np.mean(e*e))

    from scipy.optimize import minimize
    x0 = np.array([C_af, C_ar])
    bounds = [(50_000, 500_000), (50_000, 500_000)]
    res = minimize(loss, x0, method="L-BFGS-B", bounds=bounds)
    Caf_fit, Car_fit = float(res.x[0]), float(res.x[1])
    pegged = (
        abs(Caf_fit - 500_000) < 1.0 or abs(Caf_fit - 50_000) < 1.0 or
        abs(Car_fit - 500_000) < 1.0 or abs(Car_fit - 50_000) < 1.0
    )
    yaw_st_fit = st_yaw_rate(v, delta, L, m, l_f, l_r, Caf_fit, Car_fit)
    df["_resid_v3_raw"] = yaw_st_fit - yaw_meas
    df["_resid_v3_raw_straight"] = np.where(straight_mask, df["_resid_v3_raw"], np.nan)
    bias_v3 = (df.groupby("seg_id")["_resid_v3_raw_straight"].transform("mean")
                  .fillna(df.groupby("seg_id")["_resid_v3_raw"].transform("mean"))).to_numpy()
    yaw_v3 = yaw_st_fit - bias_v3
    resid_v3 = yaw_v3 - yaw_meas
    results["V3"] = per_regime_rmse(resid_v3, regime)
    results["V3_fit"] = {"C_af": Caf_fit, "C_ar": Car_fit, "pegged": pegged,
                         "C_af_prior": C_af, "C_ar_prior": C_ar}

    # V4: first-order yaw-rate lag on V3 yaw_st_fit (apply lag to bias-corrected V3 pred).
    # fit tau via 1-D scan on a 5% subsample for speed
    rng = np.random.default_rng(0)
    sub_idx = rng.choice(len(df), size=min(len(df), 60_000), replace=False)
    sub_idx.sort()
    seg_sub = seg_ids[sub_idx]; t_sub = t_s[sub_idx]
    # Lag must operate on contiguous per-segment series; use full arrays.
    def eval_tau(tau):
        lag_pred = apply_lag(seg_ids, t_s, yaw_v3, tau)
        e = lag_pred - yaw_meas
        return rmse(e)
    taus = [0.02, 0.05, 0.08, 0.12, 0.18, 0.25, 0.35, 0.5, 0.75, 1.0]
    tau_results = {tau: eval_tau(tau) for tau in taus}
    tau_best = min(tau_results, key=tau_results.get)
    yaw_v4 = apply_lag(seg_ids, t_s, yaw_v3, tau_best)
    resid_v4 = yaw_v4 - yaw_meas
    results["V4"] = per_regime_rmse(resid_v4, regime)
    results["V4_fit"] = {"tau_best_s": tau_best, "tau_scan_rmse": tau_results}

    # Marginal drops (strict, V_prev -> V_this on overall RMSE)
    order = ["V0","V1","V2","V3","V4"]
    margins = {}
    for i in range(1, len(order)):
        prev = results[order[i-1]]["overall"]["rmse"]
        cur = results[order[i]]["overall"]["rmse"]
        margins[order[i]] = {"prev": prev, "cur": cur, "drop": prev - cur, "pct": (prev - cur)/prev*100 if prev>0 else float("nan")}
    results["marginal_drops"] = margins
    results["meta"] = {
        "platform": PLATFORM,
        "n_samples": int(len(df)),
        "n_segments": int(df["seg_id"].nunique()),
        "per_regime_n": {r: int((regime==r).sum()) for r in ("straight","steady","transient")},
    }

    with open(OUT / "ladder.json", "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
