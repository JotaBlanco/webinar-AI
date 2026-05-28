"""Canonical-eval reconstruction of angleA-m4-agent-02's V4 model.

V4 = V3 (Linear-ST with fit Cα + per-segment straight bias)
     − Ridge residual learner predicting V3 residual from
       features [v, |a_y_pred|, |δ|, sign(δ̇)].

For canonical eval (545 Ford segments across two platforms):
  - V3: Linear-ST with agent's fitted Cf/Cr (427029, 483737) using each
        segment's own platform parameters (L, l_f, l_r, m, I_z) — this is
        the agent's "model" applied to each platform; the leakage_note in
        the YAML explicitly anticipates platform-specific coefficients.
  - Per-segment straight bias: re-derived per segment from straight samples
        (|δ_road| < 0.01) with v_mps > 2.0 — agent's own calibration step.
  - Ridge: trained ONCE on agent's 60 Mach-E segments (first sorted), then
        applied globally. (Agent uses LOSO per-segment within Mach-E; for
        unseen platforms / segments the closest reconstruction is a single
        global model.)

Pooled-sample RMSE over all qualifying samples (v_mps > 2.0).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path("/Users/javiquix/Desktop/quixdev/webinar-AI")
AGENT = REPO / "webinar-angle-A/module-4/agent-02"

sys.path.insert(0, str(AGENT / "skills/lateral-fidelity-triage"))
sys.path.insert(0, str(AGENT / "code"))

import triage  # type: ignore
from parameters import PARAM_BY_PLATFORM  # type: ignore
from sklearn.linear_model import Ridge  # type: ignore

# Agent's fitted Cα from out/ladder_results.json
CF_FIT = 427029.1671174572
CR_FIT = 483736.5465673796

REGIME_DELTA_THR = 0.01

SEGMENT_GLOBS = [
    ("FORD_MUSTANG_MACH_E_MK1", "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv"),
    ("FORD_F_150_LIGHTNING_MK1", "data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv"),
]


def features_from_segment(df: pd.DataFrame) -> np.ndarray:
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt > 0, dt, 0.02)
    delta = df["delta_road_rad"].to_numpy()
    ddelta = np.gradient(delta) / dt
    v = df["v_mps"].to_numpy()
    a_y = df["a_y_pred_mps2"].to_numpy() if "a_y_pred_mps2" in df.columns else np.zeros(len(df))
    return np.column_stack([v, np.abs(a_y), np.abs(delta), np.sign(ddelta)])


def v3_pred_for_segment(df: pd.DataFrame, platform: str) -> tuple[np.ndarray, float]:
    """Return (V3 prediction in rad/s, bias_subtracted)."""
    P = PARAM_BY_PLATFORM[platform]
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    meas = df["yaw_rate_meas_rads"].to_numpy()
    # Linear-ST with fitted Cα and this platform's L, l_f, l_r, m, I_z
    st = triage.linear_st_yaw_rate(v, delta, P.L, P.l_f, P.l_r, P.m, P.I_z, CF_FIT, CR_FIT)
    # per-segment bias on straight samples (mirror agent's approach: agent uses
    # __regime__ == straight which is |delta| < 0.01 — no v threshold there;
    # we use the same definition for fidelity)
    straight = np.abs(delta) < REGIME_DELTA_THR
    raw_resid = st - meas
    if straight.sum() >= 20:
        bias = float(np.nanmean(raw_resid[straight]))
    else:
        bias = 0.0
    pred = st - bias  # V3_pred (subtract bias from pred so residual = pred - meas - bias)
    return pred, bias


def collect_segments():
    out = []
    for platform, glob_rel in SEGMENT_GLOBS:
        glob_pat = glob_rel.split("**/", 1)
        root = REPO / glob_pat[0]
        for p in sorted(root.rglob("sim.csv")):
            out.append((platform, p))
    return out


def train_ridge_on_mach_e(segments) -> Ridge:
    """Replicate the agent's V4: train on Mach-E V3 residuals.

    Agent uses first 60 Mach-E segments (sorted). We use the same set.
    """
    machE_segs = [p for plat, p in segments if plat == "FORD_MUSTANG_MACH_E_MK1"][:60]
    X_list = []
    y_list = []
    for p in machE_segs:
        df = pd.read_csv(p)
        platform = "FORD_MUSTANG_MACH_E_MK1"
        v3_pred, _bias = v3_pred_for_segment(df, platform)
        meas = df["yaw_rate_meas_rads"].to_numpy()
        y = v3_pred - meas  # V3 residual (what Ridge predicts)
        X = features_from_segment(df)
        mask = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
        X_list.append(X[mask])
        y_list.append(y[mask])
    X_all = np.vstack(X_list)
    y_all = np.concatenate(y_list)
    model = Ridge(alpha=1.0).fit(X_all, y_all)
    print(f"Ridge trained on {len(machE_segs)} Mach-E segs, {len(y_all)} rows")
    print(f"  coefs={model.coef_} intercept={model.intercept_}")
    return model


def main():
    segments = collect_segments()
    print(f"Found {len(segments)} canonical segments")
    n_mach = sum(1 for p, _ in segments if p == "FORD_MUSTANG_MACH_E_MK1")
    n_f150 = sum(1 for p, _ in segments if p == "FORD_F_150_LIGHTNING_MK1")
    print(f"  Mach-E: {n_mach}  F-150: {n_f150}")

    ridge = train_ridge_on_mach_e(segments)

    # Streaming RMSE accumulators
    sse_baseline = 0.0
    sse_agent = 0.0
    n_samples = 0
    n_segments_used = 0

    for i, (platform, csv_path) in enumerate(segments):
        df = pd.read_csv(csv_path)
        v = df["v_mps"].to_numpy()
        meas = df["yaw_rate_meas_rads"].to_numpy()
        baseline_pred = df["yaw_rate_pred_rads"].to_numpy()

        v3_pred, _bias = v3_pred_for_segment(df, platform)
        X = features_from_segment(df)
        ridge_pred = ridge.predict(X)
        v4_pred = v3_pred - ridge_pred  # V4_pred = V3_pred - predicted_residual

        # Sample filter: v_mps > 2.0 AND finite truth/pred
        mask = (v > 2.0) & np.isfinite(meas) & np.isfinite(baseline_pred) & np.isfinite(v4_pred)
        if mask.sum() == 0:
            continue
        eb = baseline_pred[mask] - meas[mask]
        ea = v4_pred[mask] - meas[mask]
        sse_baseline += float(np.sum(eb * eb))
        sse_agent += float(np.sum(ea * ea))
        n_samples += int(mask.sum())
        n_segments_used += 1
        if (i + 1) % 100 == 0:
            print(f"  processed {i+1}/{len(segments)} segments, n_samples={n_samples}")

    baseline_rmse = math.sqrt(sse_baseline / n_samples)
    agent_rmse = math.sqrt(sse_agent / n_samples)

    CANONICAL_BASELINE = 0.014740020892723483
    improvement_pct = (CANONICAL_BASELINE - agent_rmse) / CANONICAL_BASELINE * 100

    notes_parts = []
    if abs(baseline_rmse - CANONICAL_BASELINE) > 1e-6:
        notes_parts.append(
            f"baseline_rmse_recomputed ({baseline_rmse:.12f}) differs from canonical "
            f"({CANONICAL_BASELINE:.12f}) by {abs(baseline_rmse - CANONICAL_BASELINE):.2e}"
        )
    notes_parts.append(
        "Agent's V4 is a LOSO ridge residual learner trained only on 60 Mach-E segments; "
        "for canonical eval the ridge was trained once on all 60 Mach-E segments and applied "
        "globally (no LOSO possible for F-150 / unseen segments). Agent's V3 fitted Cα "
        "(427029/483737, Mach-E only) is reused; each segment uses its own platform's "
        "geometry/mass params. Per-segment straight bias is recomputed per canonical segment "
        "from its own straights, matching agent's calibration step."
    )

    result = {
        "agent_id": "angleA-m4-agent-02",
        "status": "ok",
        "reason": None,
        "reconstruction_method": "json-coeffs + imported-function",
        "reconstruction_summary": (
            "Reconstructed V4 = Linear-ST(fitted Cf=427029, Cr=483737 from "
            "out/ladder_results.json, per-platform geometry) − per-segment straight "
            "bias − Ridge(features [v, |a_y_pred|, |δ|, sign(δ̇)]) trained globally on "
            "the agent's 60 Mach-E segments' V3 residuals. Imported triage.linear_st_yaw_rate."
        ),
        "n_segments": n_segments_used,
        "n_samples_after_filter": n_samples,
        "baseline_rmse": CANONICAL_BASELINE,
        "baseline_rmse_recomputed": baseline_rmse,
        "agent_rmse": agent_rmse,
        "improvement_pct": improvement_pct,
        "notes": " ".join(notes_parts),
    }

    out_path = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/_grade/20260527-164838/canonical/angleA-m4-agent-02.json")
    out_path.write_text(json.dumps(result, indent=2))
    print(f"\nWrote {out_path}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
