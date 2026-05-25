"""Lateral-fidelity attribution — run baseline KS, then incremental upgrades,
score each on a common set of Ford sim segments.

Speed-known lateral-only contract is honoured: v_meas and delta_road_rad from
the CSV are *given* and never re-estimated. The only thing we vary is the
lateral-dynamics model (yaw-rate predictor) and the residual estimator.

Outputs (written to module root):
- report.md         — attribution table + narrative
- report.png        — predicted vs measured psi-dot overlay (transient segment)

Run:
    python3 tools/lateral_fidelity.py
"""
from __future__ import annotations

import json
import sys
import glob
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Sandbox path to the canonical module-root symlinks
MODULE_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = MODULE_ROOT / "data" / "sim" / "segments"
CODE_DIR = MODULE_ROOT / "code"

sys.path.insert(0, str(CODE_DIR))
from parameters import PARAM_BY_PLATFORM, MachEST, F150LightningST  # type: ignore

PLATFORM_DIRS = {
    "FORD_MUSTANG_MACH_E_MK1": MachEST,
    "FORD_F_150_LIGHTNING_MK1": F150LightningST,
}


# --------------------------------------------------------------------------- #
# 1. Load the Ford segments                                                    #
# --------------------------------------------------------------------------- #
def load_segments() -> list[dict]:
    """Return a list of dicts, one per Ford sim.csv."""
    segs = []
    for plat in PLATFORM_DIRS:
        for csv in sorted((DATA_DIR / plat).glob("*/*/*/sim.csv")):
            df = pd.read_csv(csv)
            # short id e.g. "MachE/08ec7b9a/1"
            short_id = f"{('MachE' if 'MUSTANG' in plat else 'F150')}/{csv.parents[2].name[:8]}/{csv.parents[0].name}"
            segs.append(
                dict(
                    platform=plat,
                    path=str(csv),
                    short_id=short_id,
                    df=df,
                    params=PLATFORM_DIRS[plat](),
                )
            )
    return segs


# --------------------------------------------------------------------------- #
# 2. Regime labelling                                                          #
# --------------------------------------------------------------------------- #
def regime_mask(df: pd.DataFrame, yaw_bias: float = 0.0) -> pd.Series:
    """Label each sample as 'straight', 'steady', or 'transient'.

    Thresholds are deliberately simple and physically motivated:
      - |yaw_rate_meas - bias|    : how much the car is actually turning
      - |delta_dot|               : how fast the driver is changing steering
                                    (a proxy for transience)

    Definitions:
      straight  : |ψ̇_corr| < 0.02 rad/s   (≈ 1.1°/s; barely-turning)
      transient : |dδ/dt|   > 0.05 rad/s  (steering moving briskly)
                  AND not straight
      steady    : the remainder (turning but driver hand is settled)
    """
    psi_dot_corr = df["yaw_rate_meas_rads"] - yaw_bias
    # numerical derivative of road-wheel angle
    delta = df["delta_road_rad"].to_numpy()
    dt = float(df["t_s"].iloc[1] - df["t_s"].iloc[0])
    ddelta = np.gradient(delta, dt)

    straight = np.abs(psi_dot_corr) < 0.02
    transient = (np.abs(ddelta) > 0.05) & (~straight)
    steady = ~straight & ~transient

    out = np.empty(len(df), dtype=object)
    out[straight] = "straight"
    out[steady] = "steady"
    out[transient] = "transient"
    return pd.Series(out, index=df.index, name="regime")


# --------------------------------------------------------------------------- #
# 3. Model variants — each returns predicted ψ̇ per-sample for one segment     #
# --------------------------------------------------------------------------- #
def predict_baseline_ks(seg: dict) -> np.ndarray:
    """Baseline = the pre-computed prediction already in the CSV.

    This *is* the existing KS model (clamp_v & clamp_delta on). No re-run
    needed; it is already there as `yaw_rate_pred_rads`.
    """
    return seg["df"]["yaw_rate_pred_rads"].to_numpy()


def predict_ks_recomputed(seg: dict) -> np.ndarray:
    """Sanity check — recompute ψ̇ = (v/L) tan(δ) from raw columns."""
    df, p = seg["df"], seg["params"]
    return (df["v_mps"].to_numpy() / p.L) * np.tan(df["delta_road_rad"].to_numpy())


def predict_linear_st(seg: dict, scale_caf: float = 1.0, scale_car: float = 1.0) -> np.ndarray:
    """Speed-known linear single-track (bicycle) yaw rate.

    State : x = [v_y, ψ̇]   (lateral velocity, yaw rate)
    Input : δ (road-wheel rad), clamped from measurement
    v     : measured, clamped each step

    Dynamics (linear tyre, small-slip, see CommonRoad ST appendix):
        v_y_dot = -(C_f+C_r)/(m v)·v_y + ((l_r C_r - l_f C_f)/(m v) - v)·ψ̇ + (C_f/m)·δ
        ψ̇_dot  = (l_r C_r - l_f C_f)/(I_z v)·v_y - (l_f² C_f + l_r² C_r)/(I_z v)·ψ̇ + (l_f C_f / I_z)·δ

    At very low speed the linear bicycle is singular (terms /v). Below v_min we
    fall back to KS for that sample.
    """
    df, p = seg["df"], seg["params"]
    Cf = p.C_alpha_f * scale_caf
    Cr = p.C_alpha_r * scale_car
    m, Iz, lf, lr, L = p.m, p.I_z, p.l_f, p.l_r, p.L
    v_meas = df["v_mps"].to_numpy()
    d_meas = df["delta_road_rad"].to_numpy()
    t = df["t_s"].to_numpy()
    N = len(t)
    psi_dot = np.zeros(N)
    v_y = 0.0
    V_MIN = 1.5  # m/s — below this, drop to KS
    # initial condition: KS yaw rate
    psi_dot[0] = (v_meas[0] / L) * np.tan(d_meas[0]) if v_meas[0] > 0 else 0.0
    for k in range(N - 1):
        dt_full = t[k + 1] - t[k]
        v = max(v_meas[k], V_MIN)
        d = d_meas[k]
        if v_meas[k] < V_MIN:
            # KS fallback below ~walking pace — linear bicycle is singular/unsafe
            psi_dot[k + 1] = (v_meas[k + 1] / L) * np.tan(d_meas[k + 1])
            v_y = 0.0
            continue
        # State derivatives (linear bicycle), frozen (v,d) over the step
        a11 = -(Cf + Cr) / (m * v)
        a12 = (lr * Cr - lf * Cf) / (m * v) - v
        a21 = (lr * Cr - lf * Cf) / (Iz * v)
        a22 = -(lf * lf * Cf + lr * lr * Cr) / (Iz * v)
        b1 = Cf / m
        b2 = lf * Cf / Iz

        # Stiffness — the fastest mode has |λ| ≈ (Cf+Cr)/(m v); at low v this
        # blows past the RK4 stability boundary on a 50-Hz grid. Substep.
        lam_max = (Cf + Cr) / (m * v)
        n_sub = max(1, int(np.ceil(lam_max * dt_full / 1.5)))
        dt = dt_full / n_sub

        def f(s):
            vy, pd = s
            return np.array([a11 * vy + a12 * pd + b1 * d,
                             a21 * vy + a22 * pd + b2 * d])
        s = np.array([v_y, psi_dot[k]])
        for _ in range(n_sub):
            k1 = f(s)
            k2 = f(s + 0.5 * dt * k1)
            k3 = f(s + 0.5 * dt * k2)
            k4 = f(s + dt * k3)
            s = s + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        v_y, psi_dot[k + 1] = s.tolist()
    return psi_dot


def fit_st_stiffness_scales(segs_train: list[dict]) -> tuple[float, float]:
    """Fit a single global (scale_caf, scale_car) that minimises summed squared
    residual on the training segments. Bounded search via SciPy.
    """
    from scipy.optimize import minimize

    def loss(theta):
        sf, sr = theta
        if sf <= 0.1 or sr <= 0.1:
            return 1e9
        ss = 0.0
        for s in segs_train:
            pred = predict_linear_st(s, scale_caf=sf, scale_car=sr)
            meas = s["df"]["yaw_rate_meas_rads"].to_numpy() - s.get("yaw_bias", 0.0)
            r = pred - meas
            ss += float(np.mean(r * r))
        return ss

    # initial: 1.0, 1.0
    res = minimize(loss, x0=[1.0, 1.0], method="Nelder-Mead",
                   options=dict(xatol=1e-3, fatol=1e-8, maxiter=200))
    return float(res.x[0]), float(res.x[1])


def predict_with_residual_learner(
    seg: dict, base_pred: np.ndarray, model_coef: dict
) -> np.ndarray:
    """Add a small data-driven residual prediction on top of `base_pred`.

    Feature vector (per-sample):  [1, delta_road, delta_road*v, a_y_pred, ddelta_dt]
    Coefficients learned globally (LinearRegression on stacked data).
    """
    df = seg["df"]
    delta = df["delta_road_rad"].to_numpy()
    v = df["v_mps"].to_numpy()
    dt = float(df["t_s"].iloc[1] - df["t_s"].iloc[0])
    ddelta = np.gradient(delta, dt)
    a_y_pred = v * base_pred
    X = np.column_stack([np.ones_like(v), delta, delta * v, a_y_pred, ddelta])
    return base_pred + X @ model_coef["beta"]


def fit_residual_learner(segs_train: list[dict], base_preds: dict) -> dict:
    """Linear regression of (meas - base_pred) on simple physical features.

    The features are chosen to express things KS/ST do not capture:
      - constant bias
      - small linear effect of delta (extra understeer)
      - delta*v term (speed-scaling of understeer)
      - a_y_pred (curvature-magnitude effect — would absorb extra slip)
      - ddelta/dt (lag / phase effect)
    """
    Xs, ys = [], []
    for s in segs_train:
        df = s["df"]
        bp = base_preds[s["short_id"]]
        meas = df["yaw_rate_meas_rads"].to_numpy() - s.get("yaw_bias", 0.0)
        delta = df["delta_road_rad"].to_numpy()
        v = df["v_mps"].to_numpy()
        dt = float(df["t_s"].iloc[1] - df["t_s"].iloc[0])
        ddelta = np.gradient(delta, dt)
        a_y_pred = v * bp
        X = np.column_stack([np.ones_like(v), delta, delta * v, a_y_pred, ddelta])
        Xs.append(X)
        ys.append(meas - bp)
    X = np.vstack(Xs)
    y = np.concatenate(ys)
    # ridge for stability
    XtX = X.T @ X + 1e-3 * np.eye(X.shape[1])
    beta = np.linalg.solve(XtX, X.T @ y)
    return dict(beta=beta, feat_names=["bias", "delta", "delta_v", "a_y_pred", "ddelta_dt"])


# --------------------------------------------------------------------------- #
# 4. Scoring                                                                   #
# --------------------------------------------------------------------------- #
def rmse(a: np.ndarray) -> float:
    a = np.asarray(a)
    return float(np.sqrt(np.mean(a * a)))


def score_variant(segs: list[dict], preds_by_seg: dict[str, np.ndarray], yaw_bias_by_seg: dict[str, float]) -> dict:
    """Return overall + regime-wise RMSEs (rad/s)."""
    regimes = ["straight", "steady", "transient"]
    all_resid, by_reg = [], {r: [] for r in regimes}
    for s in segs:
        df = s["df"]
        meas = df["yaw_rate_meas_rads"].to_numpy() - yaw_bias_by_seg.get(s["short_id"], 0.0)
        pred = preds_by_seg[s["short_id"]]
        resid = pred - meas
        all_resid.append(resid)
        reg = regime_mask(df, yaw_bias=yaw_bias_by_seg.get(s["short_id"], 0.0)).to_numpy()
        for r in regimes:
            mask = (reg == r)
            if mask.any():
                by_reg[r].append(resid[mask])
    out = {"overall": rmse(np.concatenate(all_resid))}
    for r in regimes:
        out[r] = rmse(np.concatenate(by_reg[r])) if by_reg[r] else float("nan")
    out["resid_flat"] = np.concatenate(all_resid)
    return out


# --------------------------------------------------------------------------- #
# 5. Main                                                                      #
# --------------------------------------------------------------------------- #
def main():
    segs = load_segments()
    assert len(segs) == 4, f"expected 4 Ford segments, got {len(segs)}"
    print("Segments:")
    for s in segs:
        print(f"  {s['short_id']}  v∈[{s['df'].v_mps.min():.1f},{s['df'].v_mps.max():.1f}] m/s  "
              f"yaw_meas_rms={rmse(s['df'].yaw_rate_meas_rads):.4f}")

    # --- per-segment yaw bias estimate (used by variants ≥ 1) ---
    yaw_bias = {s["short_id"]: 0.0 for s in segs}
    yaw_bias_estimated = {}
    for s in segs:
        df = s["df"]
        mask = (np.abs(df["delta_road_rad"]) < 0.001) & (np.abs(df["a_lat_meas_mps2"]) < 0.2)
        if mask.sum() > 10:
            yaw_bias_estimated[s["short_id"]] = float(df["yaw_rate_meas_rads"][mask].mean())
        else:
            yaw_bias_estimated[s["short_id"]] = 0.0
    print("\nEstimated per-segment yaw biases (rad/s) from near-straight samples:")
    for k, v in yaw_bias_estimated.items():
        print(f"  {k}:  {v:+.5f}")

    variants = {}

    # -------- v0: Baseline KS, no bias subtraction --------
    base_preds = {s["short_id"]: predict_baseline_ks(s) for s in segs}
    variants["v0_baseline_KS"] = score_variant(segs, base_preds, yaw_bias)

    # -------- v1: KS + per-segment yaw bias --------
    variants["v1_KS_plus_yaw_bias"] = score_variant(segs, base_preds, yaw_bias_estimated)

    # -------- v2: Linear ST (openpilot-canonical C_alpha) --------
    st_preds = {}
    for s in segs:
        s["yaw_bias"] = yaw_bias_estimated[s["short_id"]]
        st_preds[s["short_id"]] = predict_linear_st(s)
    variants["v2_LinearST_prior_Calpha"] = score_variant(segs, st_preds, yaw_bias_estimated)

    # -------- v3: Linear ST with fitted (scale_caf, scale_car) --------
    sf, sr = fit_st_stiffness_scales(segs)
    print(f"\nFitted ST C_alpha scales: front={sf:.3f}  rear={sr:.3f}")
    st_fit_preds = {s["short_id"]: predict_linear_st(s, scale_caf=sf, scale_car=sr) for s in segs}
    variants["v3_LinearST_fit_Calpha"] = score_variant(segs, st_fit_preds, yaw_bias_estimated)

    # -------- v4: ST (fitted) + small residual learner --------
    coef = fit_residual_learner(segs, st_fit_preds)
    learned_preds = {s["short_id"]: predict_with_residual_learner(s, st_fit_preds[s["short_id"]], coef)
                     for s in segs}
    variants["v4_ST_plus_residual_learner"] = score_variant(segs, learned_preds, yaw_bias_estimated)

    # ----------- Attribution table -----------
    print("\n" + "=" * 92)
    print(f"{'variant':32s}  {'RMSE':>8s} {'straight':>9s} {'steady':>9s} {'transient':>10s}  {'Δ_vs_prev':>10s}  {'%var_closed':>11s}")
    var0 = float(np.var(variants["v0_baseline_KS"]["resid_flat"]))
    prev_overall = None
    rows = []
    for name, m in variants.items():
        var_this = float(np.var(m["resid_flat"]))
        pct = 100.0 * (1.0 - var_this / var0)
        delta = (m["overall"] - prev_overall) if prev_overall is not None else 0.0
        rows.append((name, m["overall"], m["straight"], m["steady"], m["transient"], delta, pct))
        prev_overall = m["overall"]
        print(f"{name:32s}  {m['overall']:8.5f} {m['straight']:9.5f} {m['steady']:9.5f} {m['transient']:10.5f}  {delta:+10.5f}  {pct:10.2f}%")

    # ----------- Save table + variant preds for use in report writer -----------
    out = dict(
        variants={k: {kk: vv for kk, vv in v.items() if kk != "resid_flat"} for k, v in variants.items()},
        rows=rows,
        yaw_bias=yaw_bias_estimated,
        seg_ids=[s["short_id"] for s in segs],
        st_scales=dict(front=sf, rear=sr),
        residual_learner=dict(
            feat=coef["feat_names"],
            beta=list(map(float, coef["beta"])),
        ),
    )
    (MODULE_ROOT / "tools" / "results.json").write_text(json.dumps(out, indent=2))

    # ----------- Figure: transient-heavy segment overlay -----------
    # F150 segment 34 — highway-speed, mid-corner, KS residual largest there.
    transient_seg = next(s for s in segs if "F150" in s["short_id"] and "/34" in s["short_id"])
    df = transient_seg["df"]
    meas_unbiased = df["yaw_rate_meas_rads"] - yaw_bias_estimated[transient_seg["short_id"]]

    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.plot(df["t_s"], meas_unbiased, color="black", lw=1.2, label="measured ψ̇ (bias-corrected)")
    ax.plot(df["t_s"], base_preds[transient_seg["short_id"]], color="#d62728", lw=0.9,
            alpha=0.85, label="v0  KS baseline")
    ax.plot(df["t_s"], st_preds[transient_seg["short_id"]], color="#2ca02c", lw=0.9,
            alpha=0.85, label="v2  Linear ST (prior Cα)")
    ax.plot(df["t_s"], st_fit_preds[transient_seg["short_id"]], color="#1f77b4", lw=0.9,
            alpha=0.85, label=f"v3  Linear ST (fit Cα: f×{sf:.2f}, r×{sr:.2f})")
    ax.plot(df["t_s"], learned_preds[transient_seg["short_id"]], color="#9467bd", lw=0.9,
            alpha=0.85, label="v4  + residual learner")
    ax.set_xlabel("t [s]")
    ax.set_ylabel("yaw rate ψ̇ [rad/s]")
    ax.set_title(f"Predicted vs measured ψ̇ — {transient_seg['short_id']} (highway, transient-heavy)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", fontsize=9, ncol=1)
    fig.tight_layout()
    out_png = MODULE_ROOT / "report.png"
    fig.savefig(out_png, dpi=120)
    print(f"\nSaved figure to {out_png}")

    return rows, yaw_bias_estimated, sf, sr, coef


if __name__ == "__main__":
    main()
