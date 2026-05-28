"""Canonical eval: angleA-m4-agent-01 — favourite V4 (ridge on V3 residuals, LOSO).

V3 = linear single-track yaw-rate with fitted C_alpha = (350000, 350000) — agent's
fit from out/ladder.json — combined with per-segment straight-line bias subtraction.
V4 = V3 + ridge regression on residual features [v, |a_y_pred|, |delta|, sign(ddelta)],
trained leave-one-segment-out across all canonical Ford segments.

Structural params (L, l_f, l_r, m, I_z) are platform-specific; pulled from
agent's code/parameters.py PARAM_BY_PLATFORM.

Pooled RMSE computed over all qualifying samples (v_mps > 2.0).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

AGENT_DIR = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-01")
sys.path.insert(0, str(AGENT_DIR / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(AGENT_DIR / "code"))

import triage  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402

DATA_ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI")
OUT_PATH = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/_grade/20260527-164838/canonical/angleA-m4-agent-01.json")

CANONICAL_BASELINE_RMSE = 0.014740020892723483

PLATFORM_GLOBS = {
    "FORD_MUSTANG_MACH_E_MK1": "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "FORD_F_150_LIGHTNING_MK1": "data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
}

# Agent's fitted C_alpha (from out/ladder.json)
CF_FIT = 350000.0
CR_FIT = 350000.0


def collect_segments():
    rows = []
    for platform, pattern in PLATFORM_GLOBS.items():
        csvs = sorted((DATA_ROOT).glob(pattern))
        for c in csvs:
            rows.append((platform, c))
    return rows


def load_segment(csv_path: Path, platform: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["__source__"] = str(csv_path)
    df["__platform__"] = platform
    return df


def main():
    segs = collect_segments()
    print(f"Found {len(segs)} canonical segments")

    # Load all into one big frame
    frames = []
    for platform, c in segs:
        frames.append(load_segment(c, platform))
    df = pd.concat(frames, ignore_index=True)
    print(f"Total rows: {len(df)}")

    # ---- compute V3 prediction per platform (per-row structural params) ----
    pred_v3 = np.empty(len(df), dtype=float)
    for platform, sub_idx in df.groupby("__platform__").groups.items():
        idx = np.asarray(sub_idx)
        p = PARAM_BY_PLATFORM[platform]
        v = df["v_mps"].to_numpy()[idx]
        delta = df["delta_road_rad"].to_numpy()[idx]
        pred_v3[idx] = triage.linear_st_yaw_rate(
            v, delta, p.L, p.l_f, p.l_r, p.m, p.I_z, CF_FIT, CR_FIT
        )

    meas = df["yaw_rate_meas_rads"].to_numpy()

    # ---- regime mask (needs t_s monotonic per segment; do per-segment) ----
    regime = np.full(len(df), "transient", dtype=object)
    for src, sub_idx in df.groupby("__source__").groups.items():
        idx = np.asarray(sub_idx)
        sub = df.iloc[idx]
        rm = triage.regime_mask(sub.reset_index(drop=True)).to_numpy()
        regime[idx] = rm
    df["regime"] = regime

    # ---- per-segment straight-line bias subtraction (V1/V3 step) ----
    biases = {}
    for src, sub_idx in df.groupby("__source__").groups.items():
        idx = np.asarray(sub_idx)
        sm = (regime[idx] == "straight")
        if sm.any():
            biases[src] = float(np.mean(pred_v3[idx][sm] - meas[idx][sm]))
        else:
            biases[src] = 0.0
    bias_arr = df["__source__"].map(biases).to_numpy()
    pred_v3_corr = pred_v3 - bias_arr
    resid_v3 = pred_v3_corr - meas

    # ---- V4: ridge on residuals, LOSO ----
    from sklearn.linear_model import Ridge
    t = df["t_s"].to_numpy()
    # per-segment dt — recompute carefully across segment boundaries
    dt = np.full(len(df), 0.02)
    for src, sub_idx in df.groupby("__source__").groups.items():
        idx = np.asarray(sub_idx)
        ts = t[idx]
        d = np.diff(ts, prepend=ts[0])
        d = np.where(d <= 0, 0.02, d)
        dt[idx] = d
    delta_all = df["delta_road_rad"].to_numpy()
    # ddelta per segment
    ddelta = np.zeros(len(df))
    for src, sub_idx in df.groupby("__source__").groups.items():
        idx = np.asarray(sub_idx)
        ddelta[idx] = np.gradient(delta_all[idx]) / dt[idx]
    a_y = df["a_y_pred_mps2"].to_numpy() if "a_y_pred_mps2" in df.columns else np.zeros(len(df))
    X = np.column_stack([
        df["v_mps"].to_numpy(),
        np.abs(a_y),
        np.abs(delta_all),
        np.sign(ddelta),
    ])
    y = resid_v3

    segs_unique = df["__source__"].unique()
    oof = np.full(len(df), np.nan)
    src_arr = df["__source__"].to_numpy()
    for i, seg in enumerate(segs_unique):
        train_mask = src_arr != seg
        test_mask = ~train_mask
        Xtr = X[train_mask]
        ytr = y[train_mask]
        # filter finite
        finite = np.isfinite(Xtr).all(axis=1) & np.isfinite(ytr)
        model = Ridge(alpha=1.0).fit(Xtr[finite], ytr[finite])
        oof[test_mask] = model.predict(X[test_mask])
        if (i + 1) % 50 == 0:
            print(f"LOSO {i+1}/{len(segs_unique)}")

    # Final agent prediction: pred_v4 = pred_v3_corr - oof_ridge_residual_prediction
    pred_v4 = pred_v3_corr - oof
    # fallback for nan oof rows
    nan_mask = ~np.isfinite(oof)
    pred_v4[nan_mask] = pred_v3_corr[nan_mask]

    # ---- canonical metrics: pooled over v_mps > 2.0 ----
    v_all = df["v_mps"].to_numpy()
    qualify = v_all > 2.0
    finite_mask = qualify & np.isfinite(pred_v4) & np.isfinite(meas)

    baseline_pred = df["yaw_rate_pred_rads"].to_numpy()
    finite_baseline = qualify & np.isfinite(baseline_pred) & np.isfinite(meas)

    baseline_rmse_recomputed = float(np.sqrt(np.mean((baseline_pred[finite_baseline] - meas[finite_baseline]) ** 2)))
    agent_rmse = float(np.sqrt(np.mean((pred_v4[finite_mask] - meas[finite_mask]) ** 2)))
    improvement_pct = (CANONICAL_BASELINE_RMSE - agent_rmse) / CANONICAL_BASELINE_RMSE * 100

    n_segments = int(len(segs_unique))
    n_samples = int(finite_mask.sum())

    notes_parts = []
    if abs(baseline_rmse_recomputed - CANONICAL_BASELINE_RMSE) > 1e-6:
        notes_parts.append(f"baseline_rmse_recomputed differs from canonical by {abs(baseline_rmse_recomputed - CANONICAL_BASELINE_RMSE):.3e}")
    notes_parts.append("V4 = V3 (linear single-track with Cf=Cr=350000 fitted on Mach-E) + per-segment straight-line bias correction + Ridge(alpha=1.0) on residuals with features [v, |a_y_pred|, |delta|, sign(ddelta)], trained leave-one-segment-out across all 545 canonical Ford segments")
    notes_parts.append("Structural params (L, l_f, l_r, m, I_z) taken per-platform from agent's parameters.py; fitted C_alpha applied uniformly across both Ford platforms as the agent shipped a single fit")
    notes = ". ".join(notes_parts)

    out = {
        "agent_id": "angleA-m4-agent-01",
        "status": "ok",
        "reason": None,
        "reconstruction_method": "json-coeffs",
        "reconstruction_summary": "Re-ran V4 (favourite): linear single-track with agent's fitted Cf=Cr=350000 + per-segment straight-line bias subtraction + Ridge(alpha=1.0) residual learner on [v, |a_y|, |delta|, sign(ddelta)] features, trained leave-one-segment-out across all 545 canonical Ford segments.",
        "n_segments": n_segments,
        "n_samples_after_filter": n_samples,
        "baseline_rmse": CANONICAL_BASELINE_RMSE,
        "baseline_rmse_recomputed": baseline_rmse_recomputed,
        "agent_rmse": agent_rmse,
        "improvement_pct": improvement_pct,
        "notes": notes,
    }
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
