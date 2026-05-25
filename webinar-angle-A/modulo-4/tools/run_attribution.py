"""Lateral fidelity attribution — V0 (KS baseline) -> V1 (KS param recalibration)
-> V2 (linear ST) -> V3 (C_alpha tuning) on Ford segments.

Honors speed-known lateral-only contract — both v and delta are clamped to the
measured signal at every step. The predicted channel under test is ψ̇.

Outputs:
  - prints the attribution table (markdown)
  - writes report.png in the module root
  - writes a JSON of the per-variant arrays for the report

Usage:
    python tools/run_attribution.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.integrate import odeint
from scipy.optimize import minimize

# Make code/ and skills/ importable
MODULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MODULE_ROOT / "code"))
sys.path.insert(0, str(MODULE_ROOT / "skills" / "lateral-fidelity-triage"))

from parameters import PARAM_BY_PLATFORM  # noqa: E402
from triage import (  # noqa: E402
    Segment,
    attribution_markdown_table,
    concat,
    concat_masks,
    discover_ford_segments,
    load_segment,
    regime_masks,
    rmse,
    score_variant,
    variance,
)


# ---------- Variant predictors ------------------------------------------------

def predict_v0(seg: Segment) -> np.ndarray:
    """Existing CSV column — KS baseline."""
    return seg.yaw_pred_v0


def predict_ks(seg: Segment, L: float, delta_scale: float = 1.0) -> np.ndarray:
    """KS yaw rate with optional re-fit of L and an i_s correction.

    `delta_scale` multiplies the road-wheel delta. Since
        delta_road = -deg2rad(delta_wheel)/i_s,
    a scale `s` on delta_road is equivalent to dividing i_s by `s`. So fitting
    `delta_scale` is fitting `i_s_new = i_s_orig / delta_scale`.
    """
    delta = seg.delta_road * delta_scale
    return (seg.v / L) * np.tan(delta)


def predict_st_linear(seg: Segment, m, I_z, l_f, l_r, C_f, C_r,
                       v_min: float = 3.0, substeps: int = 10) -> np.ndarray:
    """Speed-known linear single-track yaw-rate.

    The 2-state linear ODE in (v_y, ψ̇) is stiff at low speed (the system
    eigenvalues scale like C/(m*v)); explicit Euler at 50 Hz blows up below
    ~5 m/s. We solve in closed form per step using the discrete-time matrix
    exponential (A·dt + I + A²·dt²/2 ... — but we just use scipy's odeint via
    matrix exponential is overkill — instead we sub-step at dt/substeps with
    explicit Euler, which is sufficient at substeps=10 for v ≥ v_min).

    For samples where v < v_min the model is ill-conditioned (sideslip
    saturates); we fall back to the KS prediction `(v/L)·tan(δ)`.

    State x = [v_y, ψ̇]. Continuous ODE:
        v_y_dot = (F_yf + F_yr)/m − v · ψ̇
        ψ̈      = (l_f·F_yf − l_r·F_yr)/I_z
        α_f    = δ − (v_y + l_f·ψ̇)/v
        α_r    =   − (v_y − l_r·ψ̇)/v
        F_yf   = C_f·α_f,  F_yr = C_r·α_r
    """
    v_arr = seg.v
    delta = seg.delta_road
    dt = seg.dt
    n = len(v_arr)
    L = l_f + l_r

    sub_dt = dt / substeps
    yaw_out = np.empty(n)
    v_y = 0.0
    yaw = float(seg.yaw_meas[0])
    yaw_out[0] = yaw

    for k in range(1, n):
        v = float(v_arr[k - 1])
        d = float(delta[k - 1])
        if v < v_min:
            # KS fallback
            yaw = (v / L) * np.tan(d)
            v_y = 0.0
        else:
            for _ in range(substeps):
                alpha_f = d - (v_y + l_f * yaw) / v
                alpha_r = -(v_y - l_r * yaw) / v
                F_yf = C_f * alpha_f
                F_yr = C_r * alpha_r
                v_y_dot = (F_yf + F_yr) / m - v * yaw
                yaw_dot = (l_f * F_yf - l_r * F_yr) / I_z
                v_y = v_y + v_y_dot * sub_dt
                yaw = yaw + yaw_dot * sub_dt
        if not np.isfinite(yaw) or abs(yaw) > 5.0:
            yaw = (float(v_arr[k]) / L) * np.tan(float(delta[k]))
            v_y = 0.0
        yaw_out[k] = yaw
    return yaw_out


# ---------- Pipeline ----------------------------------------------------------

def main() -> int:
    data_root = str(MODULE_ROOT / "data")
    seg_paths = discover_ford_segments(data_root)
    print(f"Found {len(seg_paths)} Ford segments")
    for p in seg_paths:
        print(f"  - {p}")

    segs = [load_segment(p) for p in seg_paths]

    # Per-segment masks then concat
    masks = concat_masks(segs)
    yaw_meas_c = concat(segs, "yaw_meas")
    yaw_v0_c = concat(segs, "yaw_pred_v0")

    base_resid = yaw_v0_c - yaw_meas_c
    base_var = variance(base_resid)

    print(f"\nRegime counts (concatenated, post-trim):"
          f" straight={masks.straight.sum()},"
          f" steady={masks.steady.sum()},"
          f" transient={masks.transient.sum()},"
          f" total={len(yaw_meas_c)}")

    # ----- V0: baseline from CSV column -----
    row_v0 = score_variant("V0 — KS baseline", yaw_v0_c, yaw_meas_c, masks,
                           base_var, prev_rmse_overall=None)

    # ----- V1: KS recalibrated. Fit (L_scale, delta_scale) per platform on
    # straight+steady samples (KS structure is near-exact in those regimes).
    # delta_scale = i_s_orig / i_s_new ; L_scale = L_new/L_orig
    fit_mask = masks.straight | masks.steady

    # Concatenate per-platform fit. Use a single global (L_scale, delta_scale)
    # per platform.
    def per_platform_fit(seg_list: list[Segment]) -> dict:
        params_by_plat = {}
        plats = sorted({s.platform for s in seg_list})
        for plat in plats:
            sub = [s for s in seg_list if s.platform == plat]
            P = PARAM_BY_PLATFORM[plat]

            # Per-segment masks for the fit subset
            seg_masks = [regime_masks(s.yaw_meas, s.dt) for s in sub]
            fit_local = np.concatenate([m.straight | m.steady for m in seg_masks])
            yaw_meas_local = np.concatenate([s.yaw_meas for s in sub])
            v_local = np.concatenate([s.v for s in sub])
            delta_local = np.concatenate([s.delta_road for s in sub])

            # Fit i_s only (via delta_scale). Hold L fixed: with the few
            # large-|δ| samples available, L is unidentifiable and joint fits
            # blow up (per ks-vs-st.md, an L move > a couple of cm signals a
            # units/sign error, not real geometry).
            def loss(d_scale):
                d_scale = float(d_scale)
                pred = (v_local / P.L) * np.tan(delta_local * d_scale)
                r = (pred - yaw_meas_local)[fit_local]
                return np.mean(r ** 2)

            from scipy.optimize import minimize_scalar
            res = minimize_scalar(loss, bounds=(0.5, 2.0), method="bounded",
                                  options={"xatol": 1e-4})
            d_scale = float(res.x)
            params_by_plat[plat] = {
                "L_orig": P.L, "L_fit": P.L,
                "i_s_orig": P.i_s, "i_s_fit": P.i_s / d_scale,
                "L_scale": 1.0, "delta_scale": d_scale,
            }
        return params_by_plat

    v1_params = per_platform_fit(segs)
    print("\nV1 KS recalibration:")
    for plat, p in v1_params.items():
        print(f"  {plat}: L {p['L_orig']:.3f} -> {p['L_fit']:.3f} m, "
              f"i_s {p['i_s_orig']:.2f} -> {p['i_s_fit']:.2f}")

    yaw_v1_list = []
    for s in segs:
        p = v1_params[s.platform]
        yaw_v1_list.append(predict_ks(s, p["L_fit"], p["delta_scale"]))
    yaw_v1_c = np.concatenate(yaw_v1_list)
    row_v1 = score_variant("V1 — KS recalibrated (L, i_s)", yaw_v1_c, yaw_meas_c,
                           masks, base_var, prev_rmse_overall=row_v0.rmse_overall)

    # ----- V2: ST with openpilot-canonical parameters -----
    yaw_v2_list = []
    for s in segs:
        P = PARAM_BY_PLATFORM[s.platform]
        yaw_v2_list.append(predict_st_linear(
            s, m=P.m, I_z=P.I_z, l_f=P.l_f, l_r=P.l_r,
            C_f=P.C_alpha_f, C_r=P.C_alpha_r))
    yaw_v2_c = np.concatenate(yaw_v2_list)
    row_v2 = score_variant("V2 — Linear ST (canonical Cα)", yaw_v2_c, yaw_meas_c,
                           masks, base_var, prev_rmse_overall=row_v1.rmse_overall)

    # ----- V3: C_alpha fit by residual minimisation, per platform -----
    def fit_calpha(seg_list: list[Segment]) -> dict:
        out = {}
        plats = sorted({s.platform for s in seg_list})
        for plat in plats:
            sub = [s for s in seg_list if s.platform == plat]
            P = PARAM_BY_PLATFORM[plat]
            yaw_meas_local = np.concatenate([s.yaw_meas for s in sub])

            def loss(x):
                c_f, c_r = x
                if c_f < 50_000 or c_r < 50_000:
                    return 1e6
                if c_f > 500_000 or c_r > 500_000:
                    return 1e6
                preds = []
                for s in sub:
                    preds.append(predict_st_linear(s, P.m, P.I_z, P.l_f, P.l_r,
                                                   c_f, c_r))
                yaw_pred = np.concatenate(preds)
                return float(np.mean((yaw_pred - yaw_meas_local) ** 2))

            res = minimize(loss, x0=[P.C_alpha_f, P.C_alpha_r],
                           method="Nelder-Mead",
                           options={"xatol": 100.0, "fatol": 1e-7, "maxiter": 200})
            out[plat] = {"C_alpha_f_orig": P.C_alpha_f, "C_alpha_r_orig": P.C_alpha_r,
                         "C_alpha_f_fit": float(res.x[0]),
                         "C_alpha_r_fit": float(res.x[1])}
        return out

    v3_params = fit_calpha(segs)
    print("\nV3 Cα tuning:")
    for plat, p in v3_params.items():
        print(f"  {plat}: C_f {p['C_alpha_f_orig']:,.0f} -> {p['C_alpha_f_fit']:,.0f}; "
              f"C_r {p['C_alpha_r_orig']:,.0f} -> {p['C_alpha_r_fit']:,.0f}")

    yaw_v3_list = []
    for s in segs:
        P = PARAM_BY_PLATFORM[s.platform]
        fp = v3_params[s.platform]
        yaw_v3_list.append(predict_st_linear(
            s, P.m, P.I_z, P.l_f, P.l_r,
            fp["C_alpha_f_fit"], fp["C_alpha_r_fit"]))
    yaw_v3_c = np.concatenate(yaw_v3_list)
    row_v3 = score_variant("V3 — ST + Cα tuned", yaw_v3_c, yaw_meas_c, masks,
                           base_var, prev_rmse_overall=row_v2.rmse_overall)

    rows = [row_v0, row_v1, row_v2, row_v3]
    table_md = attribution_markdown_table(rows)
    print("\n" + table_md)

    # Pick the most transient-rich segment for the figure
    seg_stds = [(np.std(s.yaw_meas), i) for i, s in enumerate(segs)]
    seg_stds.sort(reverse=True)
    fig_idx = seg_stds[0][1]
    print(f"\nFigure segment: {segs[fig_idx].path} (std={seg_stds[0][0]:.3f})")

    # Build figure
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    s = segs[fig_idx]
    yaw_v0_s = predict_v0(s)
    p1 = v1_params[s.platform]
    yaw_v1_s = predict_ks(s, p1["L_fit"], p1["delta_scale"])
    P = PARAM_BY_PLATFORM[s.platform]
    yaw_v2_s = predict_st_linear(s, P.m, P.I_z, P.l_f, P.l_r,
                                 P.C_alpha_f, P.C_alpha_r)
    p3 = v3_params[s.platform]
    yaw_v3_s = predict_st_linear(s, P.m, P.I_z, P.l_f, P.l_r,
                                 p3["C_alpha_f_fit"], p3["C_alpha_r_fit"])

    fig, ax = plt.subplots(figsize=(13, 6))
    ax.plot(s.t, s.yaw_meas, color="black", lw=1.4, label="measured ψ̇")
    ax.plot(s.t, yaw_v0_s, color="tab:red", lw=1.0, alpha=0.85, label="V0 — KS baseline")
    ax.plot(s.t, yaw_v1_s, color="tab:orange", lw=1.0, alpha=0.85, label="V1 — KS recalibrated")
    ax.plot(s.t, yaw_v2_s, color="tab:green", lw=1.0, alpha=0.85, label="V2 — Linear ST")
    ax.plot(s.t, yaw_v3_s, color="tab:blue", lw=1.0, alpha=0.85, label="V3 — ST + Cα tuned")
    ax.set_xlabel("t [s]")
    ax.set_ylabel("yaw rate ψ̇ [rad/s]")
    ax.set_title(f"Predicted vs measured yaw rate — {s.platform}\n{Path(s.path).parent}")
    ax.grid(alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(MODULE_ROOT / "report.png", dpi=130)
    print(f"\nWrote {MODULE_ROOT / 'report.png'}")

    # Dump artefacts for the report
    payload = {
        "segments": [s.path for s in segs],
        "regime_counts": {
            "straight": int(masks.straight.sum()),
            "steady": int(masks.steady.sum()),
            "transient": int(masks.transient.sum()),
            "total": int(len(yaw_meas_c)),
        },
        "v1_params": v1_params,
        "v3_params": v3_params,
        "rows": [
            {
                "variant": r.variant,
                "rmse_overall": r.rmse_overall,
                "rmse_straight": r.rmse_straight,
                "rmse_steady": r.rmse_steady,
                "rmse_transient": r.rmse_transient,
                "delta_overall_vs_prev": r.delta_overall_vs_prev,
                "pct_variance_closed": r.pct_variance_closed,
            } for r in rows
        ],
        "figure_segment": segs[fig_idx].path,
        "table_md": table_md,
    }
    (MODULE_ROOT / "tools" / "_artefacts.json").write_text(json.dumps(payload, indent=2))
    print(f"Wrote {MODULE_ROOT / 'tools' / '_artefacts.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
