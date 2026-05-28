"""Variant ladder runner for lateral-fidelity-triage on Ford Mach-E."""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
CODE_DIR = AGENT_ROOT / "code"
DATA_DIR = AGENT_ROOT / "data"
SKILL_DIR = AGENT_ROOT / "skills" / "lateral-fidelity-triage"
OUT_DIR = AGENT_ROOT / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(CODE_DIR))
sys.path.insert(0, str(SKILL_DIR))

import triage  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402


PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
MAX_SEGMENTS = 80  # cap for runtime; sample of Mach-E segments


def per_regime_rmse_for(resid: np.ndarray, reg: pd.Series) -> dict[str, float]:
    out = {"overall": triage.rmse(resid)}
    for r in ("straight", "steady", "transient"):
        mask = (reg == r).to_numpy()
        sub = resid[mask]
        out[r] = triage.rmse(sub) if sub.size else float("nan")
    return out


def main() -> None:
    seg_csvs = sorted((DATA_DIR / "sim" / "segments" / PLATFORM).rglob("sim.csv"))
    print(f"[info] discovered {len(seg_csvs)} Mach-E segments; using up to {MAX_SEGMENTS}")
    seg_csvs = seg_csvs[:MAX_SEGMENTS]

    df = triage.load_many(seg_csvs)
    print(f"[info] loaded rows: {len(df):,}")

    # Drop rows with NaN truth (Mach-E should be fine but be defensive)
    df = df.dropna(subset=["yaw_rate_meas_rads", "v_mps", "delta_road_rad"]).reset_index(drop=True)

    p = PARAM_BY_PLATFORM[PLATFORM]
    L, l_f, l_r, m, I_z = p.L, p.l_f, p.l_r, p.m, p.I_z
    Cf_prior, Cr_prior = p.C_alpha_f, p.C_alpha_r
    print(f"[params] L={L} l_f={l_f} l_r={l_r} m={m} I_z={I_z} Cf={Cf_prior} Cr={Cr_prior}")

    reg = triage.regime_mask(df)
    n_by_reg = reg.value_counts().to_dict()
    print(f"[regime] counts: {n_by_reg}")

    meas = df["yaw_rate_meas_rads"].to_numpy()
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()

    # Sanity: correlation
    mask_corn = (reg != "straight").to_numpy()
    if mask_corn.sum() > 10:
        c = np.corrcoef(delta[mask_corn], meas[mask_corn])[0, 1]
        print(f"[sanity] corr(delta, yaw_meas) on cornering = {c:+.3f}  (should be > 0)")

    results: dict[str, dict[str, float]] = {}

    # V0 — baseline: use existing yaw_rate_resid_rads as-is
    resid_v0 = df["yaw_rate_resid_rads"].to_numpy()
    results["V0_baseline"] = per_regime_rmse_for(resid_v0, reg)

    # V1 — KS recalibrated: ψ̇ = (v/L) tan(δ) with canonical L + per-segment yaw-gyro bias on straight samples
    pred_v1_raw = triage.ks_yaw_rate(v, delta, L)
    # Per-segment bias on straight samples — bias = mean(pred - meas) on straight
    bias = np.zeros(len(df))
    straight_mask = (reg == "straight").to_numpy()
    seg_ids = df["__source__"].to_numpy()
    biases = {}
    for sid in np.unique(seg_ids):
        sm = (seg_ids == sid) & straight_mask
        if sm.sum() >= 50:  # need enough samples
            b = float(np.nanmean(pred_v1_raw[sm] - meas[sm]))
        else:
            b = 0.0
        biases[sid] = b
        bias[seg_ids == sid] = b
    pred_v1 = pred_v1_raw - bias
    resid_v1 = pred_v1 - meas
    results["V1_KS_recal"] = per_regime_rmse_for(resid_v1, reg)
    print(f"[V1] median per-segment bias subtracted = {np.median(list(biases.values())):+.5f} rad/s")

    # V2 — Linear ST with prior C_alpha
    pred_v2 = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, Cf_prior, Cr_prior)
    # Apply same per-segment bias correction for fairness (V1 added bias as a DOF)
    pred_v2_adj = pred_v2 - bias
    resid_v2 = pred_v2_adj - meas
    results["V2_ST_prior_Ca"] = per_regime_rmse_for(resid_v2, reg)

    # V3 — Linear ST with fit C_alpha. The skill's fit_c_alpha uses one starting
    # point; on this loss surface there are sharp ridges, so we multistart and keep best.
    from scipy.optimize import minimize as _minimize
    bounds = (5e4, 5e5)
    def _loss(x):
        cf, cr = x
        pred = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf, cr)
        e = pred - meas
        e = e[np.isfinite(e)]
        return float(np.sqrt(np.mean(e ** 2))) if e.size else float("inf")
    best = (float("inf"), None)
    for x0 in [(1.5e5, 1.5e5), (2e5, 2e5), (Cf_prior, Cr_prior), (1e5, 3e5), (3e5, 5e5)]:
        r = _minimize(_loss, x0, method="L-BFGS-B", bounds=[bounds, bounds])
        if r.fun < best[0]:
            best = (r.fun, r.x)
    cf_fit, cr_fit = float(best[1][0]), float(best[1][1])
    pegged = (abs(cf_fit - bounds[1]) < 1.0) or (abs(cr_fit - bounds[1]) < 1.0)
    print(f"[V3] multistart fit C_alpha_f={cf_fit:,.0f}  C_alpha_r={cr_fit:,.0f}  pegged={pegged}  loss={best[0]:.5f}")
    pred_v3 = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf_fit, cr_fit)
    pred_v3_adj = pred_v3 - bias
    resid_v3 = pred_v3_adj - meas
    results["V3_ST_fit_Ca"] = per_regime_rmse_for(resid_v3, reg)

    # V4 — residual learner with LOSO CV on V3 residuals
    df_v4 = df.copy()
    df_v4["__resid_v3__"] = resid_v3
    try:
        oof, info = triage.residual_learner_loo(df_v4, residual_col="__resid_v3__")
        # V4 residual = V3 residual minus OOF prediction
        resid_v4 = resid_v3 - oof
        # Anywhere oof is nan (shouldn't happen since every row has a fold), fall back to V3
        bad = ~np.isfinite(resid_v4)
        resid_v4[bad] = resid_v3[bad]
        results["V4_resid_learner_LOSO"] = per_regime_rmse_for(resid_v4, reg)
        print(f"[V4] oof_rmse on V3 residuals = {info['oof_rmse']:.5f}")
    except Exception as e:
        print(f"[V4] FAILED: {e}")
        results["V4_resid_learner_LOSO"] = {"overall": float("nan"), "straight": float("nan"),
                                            "steady": float("nan"), "transient": float("nan")}

    # Write CSV
    rows = []
    keys = ["V0_baseline", "V1_KS_recal", "V2_ST_prior_Ca", "V3_ST_fit_Ca", "V4_resid_learner_LOSO"]
    prev_overall = None
    for k in keys:
        r = results[k]
        marg = float("nan") if prev_overall is None else (prev_overall - r["overall"])
        rows.append({"variant": k, "overall": r["overall"],
                     "straight": r["straight"], "steady": r["steady"], "transient": r["transient"],
                     "marginal_drop": marg})
        prev_overall = r["overall"]
    out_df = pd.DataFrame(rows)
    out_csv = OUT_DIR / "ladder_results.csv"
    out_df.to_csv(out_csv, index=False)
    print(f"[done] wrote {out_csv}")
    print(out_df.to_string(index=False))

    # Print compact summary for the report
    total_drop = results["V0_baseline"]["overall"] - results[keys[-1]]["overall"]
    sum_marg = sum(x for x in out_df["marginal_drop"].dropna())
    print(f"[summary] total drop V0->V_last = {total_drop:.5f};   sum of marginals = {sum_marg:.5f}")
    print(f"[summary] fit Cf/Cr = {cf_fit:.0f} / {cr_fit:.0f}  pegged={pegged}")


if __name__ == "__main__":
    main()
