"""Lateral-fidelity attribution: KS baseline → incremental upgrades.

Operates entirely on the pre-generated Ford simdata CSVs under
data/sim/segments/FORD_*. Those CSVs already contain the speed-known
KS prediction (yaw_rate_pred_rads) alongside the measured truth
(yaw_rate_meas_rads) and the inputs (delta_road_rad, v_mps), so we can
re-implement each model variant in closed form without re-decoding any
rlog. This keeps every variant on exactly the same time grid and the
same input pair (v_meas, delta_meas) — i.e. honours the speed-known
lateral-only contract.

Variants:
  v0_ks_stock      Stock KS from CSV column.
  v1_ks_Leff       KS with an effective wheelbase L_eff fit per platform.
  v2_st_canonical  Linear single-track using openpilot C_alpha values.
  v3_st_calibrated ST with an understeer-gradient scalar fit per platform.
  v4_st_residual   v3 + small ridge regression on (v, a_y_pred, ddelta).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

MODULE = Path(__file__).resolve().parents[1]
SIM_BASE = MODULE / "data" / "sim" / "segments"

PLATFORMS = ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1")

# Stock openpilot-canonical params per platform (mirrors code/parameters.py)
PARAMS = {
    "FORD_MUSTANG_MACH_E_MK1": dict(
        L=2.984, m=2336.0, I_z=4879.05, l_f=1.3130, l_r=1.671,
        C_af=286_551, C_ar=355_912,
    ),
    "FORD_F_150_LIGHTNING_MK1": dict(
        L=3.70, m=3084.0, I_z=9903.37, l_f=1.628, l_r=2.072,
        C_af=378_307, C_ar=469_878,
    ),
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@dataclass
class Segment:
    platform: str
    seg_id: str
    df: pd.DataFrame  # columns: t, delta, v, a_long, yaw_meas, yaw_pred_stock
    yaw_bias: float = 0.0   # estimated gyro bias subtracted from yaw_meas


def _estimate_yaw_bias(yaw_meas: np.ndarray, delta: np.ndarray, v: np.ndarray) -> float:
    """Estimate yaw-rate gyro bias from samples with negligible lateral input.

    Standard IMU procedure: when delta is near zero and v is non-trivial
    (so the car is rolling roughly straight), any persistent non-zero
    yaw_meas is sensor bias. We take the median over those samples for
    robustness. Falls back to the full-segment median if there are too few
    quasi-straight samples.
    """
    straight = (np.abs(delta) < 0.005) & (v > 1.0)
    if straight.sum() >= 200:
        return float(np.median(yaw_meas[straight]))
    return float(np.median(yaw_meas))


def discover_segments() -> list[Segment]:
    segs: list[Segment] = []
    for plat in PLATFORMS:
        mani = json.loads((SIM_BASE / plat / "manifest.json").read_text())
        for item in mani["segments"]:
            csv_path = MODULE / "data" / "sim" / item["csv_path"]
            df_raw = pd.read_csv(csv_path)
            yaw_raw = df_raw["yaw_rate_meas_rads"].to_numpy()
            delta   = df_raw["delta_road_rad"].to_numpy()
            v       = df_raw["v_mps"].to_numpy()
            bias = _estimate_yaw_bias(yaw_raw, delta, v)
            df = pd.DataFrame({
                "t":         df_raw["t_s"].to_numpy(),
                "delta":     delta,
                "v":         v,
                "a_long":    df_raw["a_long_mps2"].to_numpy(),
                "yaw_meas":  yaw_raw - bias,            # bias-corrected truth
                "yaw_pred_stock": df_raw["yaw_rate_pred_rads"].to_numpy(),
                "a_y_meas":  df_raw["a_lat_meas_mps2"].to_numpy(),
            })
            seg_id = f"{plat[:5]}_{item['device'][:6]}_{item['idx']}"
            segs.append(Segment(plat, seg_id, df, yaw_bias=bias))
    return segs


# ---------------------------------------------------------------------------
# Regime classification
# ---------------------------------------------------------------------------

def classify_regimes(df: pd.DataFrame) -> np.ndarray:
    """Return an array of regime labels per sample.

    Definitions (chosen to be physically meaningful at highway/urban speeds):
      - straight        : |yaw_meas| < 0.02 rad/s  (≈1.1 deg/s)  AND |a_y_meas| < 0.5 m/s²
      - steady-state    : |yaw_meas| ≥ 0.02 rad/s AND |yaw_jerk| < 0.10 rad/s²
                          (cornering with low angular jerk = settled turn)
      - transient       : everything else (build-up, release, lane-change,
                          countersteer, gust correction)

    The 0.02 rad/s straight threshold is what a Ford VSC system treats as
    "going straight" for ESC arming. The 0.10 rad/s² jerk threshold is set
    so steady-state cornering covers the bulk of constant-radius highway
    curves; tighter would over-count noise as transient. Both thresholds
    are applied to MEASURED quantities so the regime split is independent
    of model variant.
    """
    yaw = df["yaw_meas"].to_numpy()
    ay  = df["a_y_meas"].to_numpy()
    t   = df["t"].to_numpy()
    dt  = float(np.median(np.diff(t)))
    yaw_jerk = np.gradient(yaw, dt)

    labels = np.full(len(df), "transient", dtype=object)
    straight_mask = (np.abs(yaw) < 0.02) & (np.abs(ay) < 0.5)
    labels[straight_mask] = "straight"
    cornering_mask = (np.abs(yaw) >= 0.02) & (np.abs(yaw_jerk) < 0.10)
    labels[cornering_mask] = "steady"
    return labels


# ---------------------------------------------------------------------------
# Model variants -- closed-form steady-state expressions
# Each takes a Segment's df and returns predicted yaw_rate (rad/s).
# We honour speed-known lateral-only: predictions are functions of
# (v_meas, delta_meas) only.
# ---------------------------------------------------------------------------

def pred_v0_ks_stock(seg: Segment) -> np.ndarray:
    return seg.df["yaw_pred_stock"].to_numpy()


def pred_v1_ks_Leff(seg: Segment, L_eff: float) -> np.ndarray:
    v = seg.df["v"].to_numpy()
    delta = seg.df["delta"].to_numpy()
    return (v / L_eff) * np.tan(delta)


def understeer_gradient(p: dict) -> float:
    """Standard linear-ST understeer gradient K_us [s²/m].

    psi_dot_ss(delta, v) = v * delta / (L + K_us * v²)
    K_us = (m / L) * (l_r/C_af - l_f/C_ar)
    """
    m   = p["m"]; L = p["L"]
    l_f = p["l_f"]; l_r = p["l_r"]
    C_af = p["C_af"]; C_ar = p["C_ar"]
    return (m / L) * (l_r / C_af - l_f / C_ar)


def pred_v2_st_canonical(seg: Segment) -> np.ndarray:
    p = PARAMS[seg.platform]
    K_us = understeer_gradient(p)
    v = seg.df["v"].to_numpy()
    delta = seg.df["delta"].to_numpy()
    return v * delta / (p["L"] + K_us * v**2)


def pred_v3_st_calibrated(seg: Segment, scale: float) -> np.ndarray:
    """ST with a multiplicative scalar on K_us (fit per platform).

    scale < 1 means car is less understeery than canonical priors say.
    scale > 1 means more understeery (softer tyres, more load transfer).
    """
    p = PARAMS[seg.platform]
    K_us = understeer_gradient(p) * scale
    v = seg.df["v"].to_numpy()
    delta = seg.df["delta"].to_numpy()
    return v * delta / (p["L"] + K_us * v**2)


# ---------------------------------------------------------------------------
# Calibration helpers (search over 1-D parameter per platform)
# ---------------------------------------------------------------------------

def _lateral_content_mask(s: Segment) -> np.ndarray:
    """Samples that actually contain lateral signal — used for parameter fits.

    We fit calibration constants only where there is real cornering input,
    so the result is not dragged toward zero by long straight stretches
    (which contribute only noise after bias removal).
    """
    d = s.df["delta"].to_numpy()
    v = s.df["v"].to_numpy()
    return (np.abs(d) > 0.005) & (v > 1.0)


def fit_L_eff(segs_plat: list[Segment]) -> float:
    """Find L_eff that minimises RMSE over lateral-content samples."""
    p = PARAMS[segs_plat[0].platform]
    L0 = p["L"]
    grid = np.linspace(0.5 * L0, 2.5 * L0, 401)
    best = (np.inf, L0)
    for L in grid:
        sse = 0.0
        n   = 0
        for s in segs_plat:
            m = _lateral_content_mask(s)
            if not m.any():
                continue
            v = s.df["v"].to_numpy()[m]
            d = s.df["delta"].to_numpy()[m]
            pred = (v / L) * np.tan(d)
            resid = s.df["yaw_meas"].to_numpy()[m] - pred
            sse += float(np.sum(resid ** 2))
            n   += len(resid)
        if n == 0:
            continue
        rmse = np.sqrt(sse / n)
        if rmse < best[0]:
            best = (rmse, L)
    return best[1]


def fit_K_us_scale(segs_plat: list[Segment]) -> float:
    """Find multiplicative scale on K_us minimising RMSE over lateral-content."""
    grid = np.linspace(-2.0, 8.0, 401)
    best = (np.inf, 1.0)
    for s_scale in grid:
        sse = 0.0
        n   = 0
        for s in segs_plat:
            m = _lateral_content_mask(s)
            if not m.any():
                continue
            pred = pred_v3_st_calibrated(s, s_scale)[m]
            resid = s.df["yaw_meas"].to_numpy()[m] - pred
            sse += float(np.sum(resid ** 2))
            n   += len(resid)
        if n == 0:
            continue
        rmse = np.sqrt(sse / n)
        if rmse < best[0]:
            best = (rmse, s_scale)
    return best[1]


# ---------------------------------------------------------------------------
# Residual learner (v4): tiny ridge regression on physically meaningful
# features. Stays "small" by using a fixed 4-feature design, trained
# leave-one-segment-out per platform so we never score on the same data
# we fit on.
# ---------------------------------------------------------------------------

def build_features(seg: Segment, yaw_pred_v3: np.ndarray) -> np.ndarray:
    """Features that proxy what linear ST still gets wrong:

    f1 = a_y_pred · |a_y_pred|     (nonlinear-tyre proxy: at high lat-G the
                                    cornering stiffness softens — quadratic
                                    sign-preserving term)
    f2 = delta_dot · v             (transient phase-lag: yaw rate lags
                                    steering during steering wheel motion)

    Deliberately small (2 features) because we have only 2 segments per
    platform and want to avoid LOO-CV variance from overfitting.
    """
    df = seg.df
    v = df["v"].to_numpy()
    d = df["delta"].to_numpy()
    t = df["t"].to_numpy()
    dt = float(np.median(np.diff(t)))
    ay_pred = v * yaw_pred_v3
    delta_dot = np.gradient(d, dt)
    return np.column_stack([
        ay_pred * np.abs(ay_pred),
        delta_dot * v,
    ])


def ridge_fit(X: np.ndarray, y: np.ndarray, lam: float = 1.0) -> np.ndarray:
    XtX = X.T @ X + lam * np.eye(X.shape[1])
    return np.linalg.solve(XtX, X.T @ y)


def predict_v4(segs: list[Segment], k_us_scale: dict[str, float]) -> dict[str, np.ndarray]:
    """Leave-one-segment-out residual learner, per platform.

    For each segment s in platform P:
      train ridge on the lateral-content residuals (yaw_meas - yaw_pred_v3)
      of the OTHER segments of P, predict on s, add the correction to v3.

    Training is restricted to lateral-content samples so the learner is
    not asked to model gyro noise on straights. Strong ridge (lam=1e3) plus
    only 2 features keeps the LOO held-out fold honest.

    Returns {seg_id: yaw_pred_v4}.
    """
    out: dict[str, np.ndarray] = {}
    for plat in PLATFORMS:
        plat_segs = [s for s in segs if s.platform == plat]
        scale = k_us_scale[plat]
        feats = {}
        v3_preds = {}
        for s in plat_segs:
            v3 = pred_v3_st_calibrated(s, scale)
            v3_preds[s.seg_id] = v3
            feats[s.seg_id] = build_features(s, v3)
        for s in plat_segs:
            train_others = [o for o in plat_segs if o.seg_id != s.seg_id]
            if not train_others:
                out[s.seg_id] = v3_preds[s.seg_id]
                continue
            X_blocks, y_blocks = [], []
            for o in train_others:
                m = _lateral_content_mask(o)
                if not m.any():
                    continue
                X_blocks.append(feats[o.seg_id][m])
                y_blocks.append(o.df["yaw_meas"].to_numpy()[m] - v3_preds[o.seg_id][m])
            if not X_blocks:
                out[s.seg_id] = v3_preds[s.seg_id]
                continue
            X_train = np.vstack(X_blocks)
            y_train = np.concatenate(y_blocks)
            w = ridge_fit(X_train, y_train, lam=1e3)
            corr = feats[s.seg_id] @ w
            out[s.seg_id] = v3_preds[s.seg_id] + corr
    return out


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def regime_rmse(yaw_meas: np.ndarray, yaw_pred: np.ndarray,
                regimes: np.ndarray) -> dict[str, float]:
    out = {}
    resid = yaw_meas - yaw_pred
    out["overall"] = float(np.sqrt(np.mean(resid ** 2)))
    for r in ("straight", "steady", "transient"):
        mask = regimes == r
        if mask.any():
            out[r] = float(np.sqrt(np.mean(resid[mask] ** 2)))
        else:
            out[r] = float("nan")
    return out


def pool_scores(segs: list[Segment], preds: dict[str, np.ndarray],
                regimes: dict[str, np.ndarray]) -> dict[str, float]:
    """Pool RMSE across ALL segments (concatenated residuals)."""
    all_meas = np.concatenate([s.df["yaw_meas"].to_numpy() for s in segs])
    all_pred = np.concatenate([preds[s.seg_id] for s in segs])
    all_reg  = np.concatenate([regimes[s.seg_id] for s in segs])
    return regime_rmse(all_meas, all_pred, all_reg)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main() -> None:
    segs = discover_segments()
    print(f"Loaded {len(segs)} segments:")
    for s in segs:
        print(f"  {s.platform:30s} {s.seg_id:35s} rows={len(s.df)}  "
              f"yaw_bias_subtracted={s.yaw_bias:+.5f} rad/s "
              f"({np.degrees(s.yaw_bias):+.2f} deg/s)")

    regimes = {s.seg_id: classify_regimes(s.df) for s in segs}
    # Report regime fractions
    all_reg = np.concatenate(list(regimes.values()))
    n = len(all_reg)
    print("\nRegime fractions (pooled):")
    for r in ("straight", "steady", "transient"):
        frac = float(np.mean(all_reg == r))
        print(f"  {r:12s}: {frac*100:5.1f}% ({int(frac*n)} samples)")

    # ----- v0 -----
    preds_v0 = {s.seg_id: pred_v0_ks_stock(s) for s in segs}

    # ----- v1: per-platform L_eff -----
    L_eff = {}
    preds_v1 = {}
    for plat in PLATFORMS:
        plat_segs = [s for s in segs if s.platform == plat]
        L_eff[plat] = fit_L_eff(plat_segs)
        for s in plat_segs:
            preds_v1[s.seg_id] = pred_v1_ks_Leff(s, L_eff[plat])
    print("\nFit L_eff per platform:")
    for plat in PLATFORMS:
        print(f"  {plat:30s} L_stock={PARAMS[plat]['L']:.3f}  "
              f"L_eff={L_eff[plat]:.3f}  Δ={L_eff[plat]-PARAMS[plat]['L']:+.3f} m")

    # ----- v2: ST canonical -----
    preds_v2 = {s.seg_id: pred_v2_st_canonical(s) for s in segs}

    # ----- v3: ST calibrated K_us scale per platform -----
    k_scale = {}
    preds_v3 = {}
    for plat in PLATFORMS:
        plat_segs = [s for s in segs if s.platform == plat]
        k_scale[plat] = fit_K_us_scale(plat_segs)
        for s in plat_segs:
            preds_v3[s.seg_id] = pred_v3_st_calibrated(s, k_scale[plat])
    print("\nFit K_us scale per platform:")
    for plat in PLATFORMS:
        K0 = understeer_gradient(PARAMS[plat])
        print(f"  {plat:30s} K_us_canonical={K0*1000:.4f} ms²/m  "
              f"scale={k_scale[plat]:.3f}  → K_us_fit={K0*k_scale[plat]*1000:.4f} ms²/m")

    # ----- v4: v3 + per-segment LOO ridge correction -----
    preds_v4 = predict_v4(segs, k_scale)

    # ----- Score -----
    rows = []
    variants = [
        ("v0_ks_stock",      preds_v0),
        ("v1_ks_Leff",       preds_v1),
        ("v2_st_canonical",  preds_v2),
        ("v3_st_calibrated", preds_v3),
        ("v4_st_residual",   preds_v4),
    ]
    baseline_resid = None
    prev_overall = None
    print("\n=== Attribution table ===")
    print(f"{'variant':20s} {'overall':>9s} {'straight':>9s} {'steady':>9s} {'transient':>10s}  {'Δ_vs_prev':>10s}  {'%var_closed':>12s}")
    table_rows = []
    for name, preds in variants:
        scores = pool_scores(segs, preds, regimes)
        all_meas = np.concatenate([s.df["yaw_meas"].to_numpy() for s in segs])
        all_pred = np.concatenate([preds[s.seg_id] for s in segs])
        resid = all_meas - all_pred
        if baseline_resid is None:
            baseline_resid = resid
            pct_var_closed = 0.0
        else:
            pct_var_closed = (1.0 - np.var(resid) / np.var(baseline_resid)) * 100.0
        delta_vs_prev = (scores["overall"] - prev_overall) if prev_overall is not None else 0.0
        prev_overall = scores["overall"]
        print(f"{name:20s} {scores['overall']:9.5f} {scores['straight']:9.5f} "
              f"{scores['steady']:9.5f} {scores['transient']:10.5f}  "
              f"{delta_vs_prev:+10.5f}  {pct_var_closed:11.2f}%")
        table_rows.append({
            "variant": name,
            "RMSE_overall":  scores["overall"],
            "RMSE_straight": scores["straight"],
            "RMSE_steady":   scores["steady"],
            "RMSE_transient":scores["transient"],
            "Delta_overall_vs_prev": delta_vs_prev,
            "pct_variance_closed": pct_var_closed,
        })

    # Persist for the report builder.
    out = {
        "segments": [
            {"platform": s.platform, "seg_id": s.seg_id, "rows": len(s.df)}
            for s in segs
        ],
        "regime_fractions": {
            r: float(np.mean(all_reg == r)) for r in ("straight", "steady", "transient")
        },
        "fits": {
            "L_eff": L_eff,
            "K_us_scale": k_scale,
            "K_us_canonical_ms2_per_m": {
                plat: understeer_gradient(PARAMS[plat]) for plat in PLATFORMS
            },
        },
        "table": table_rows,
    }
    (MODULE / "tools" / "attribution_results.json").write_text(json.dumps(out, indent=2))

    # Save per-segment predictions for the plotter.
    np.savez(
        MODULE / "tools" / "preds.npz",
        **{
            f"{name}__{s.seg_id}": preds[s.seg_id]
            for name, preds in variants
            for s in segs
        },
        **{f"t__{s.seg_id}": s.df["t"].to_numpy() for s in segs},
        **{f"meas__{s.seg_id}": s.df["yaw_meas"].to_numpy() for s in segs},
        **{f"regime__{s.seg_id}": regimes[s.seg_id].astype(str) for s in segs},
    )
    print("\nWrote tools/attribution_results.json and tools/preds.npz")


if __name__ == "__main__":
    main()
