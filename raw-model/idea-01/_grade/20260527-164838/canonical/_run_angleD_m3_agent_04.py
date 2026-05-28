#!/usr/bin/env python3
"""Canonical eval for angleD-m3-agent-04.

Reconstructs agent's "best" model: V4 = V3 (Linear ST with fit C_alpha) +
per-segment bias correction - Ridge residual learner trained on agent's 60
Mach-E training segments.

The agent shipped V4 as a LOO-trained Ridge on `[v, |a_y|, |delta|, sign(ddelta)]`
learning the V3 residual on 60 Mach-E segments. For the canonical run we:
  - V3: use platform-specific (m, I_z, l_f, l_r, L) and the agent's reported
    Cf=Cr=1.5e5 N/rad (the fit stalled at x0, per the agent's REPORT).
  - Per-segment bias on straight-line samples (|delta|<0.01).
  - Ridge: train ONCE on the agent's 60 Mach-E training segments (V3 residual),
    then apply to all 545 canonical Ford segments (both Mach-E and F-150
    Lightning).
"""
from __future__ import annotations
import glob
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

REPO = Path("/Users/javiquix/Desktop/quixdev/webinar-AI")
OUT_JSON = REPO / "raw-model/idea-01/_grade/20260527-164838/canonical/angleD-m3-agent-04.json"

CANON_BASELINE = 0.014740020892723483

# Platform parameters lifted verbatim from
# webinar-angle-D/module-3/agent-04/code/parameters.py
PARAMS = {
    "FORD_MUSTANG_MACH_E_MK1": dict(
        L=2.984, l_f=1.3130, l_r=1.671, m=2336.0, I_z=4879.05,
    ),
    "FORD_F_150_LIGHTNING_MK1": dict(
        L=3.70, l_f=1.628, l_r=2.072, m=3084.0, I_z=9903.37,
    ),
}

# Per the agent's REPORT and run_ladder output: V3's fit_c_alpha stalled at x0.
CF = 1.5e5
CR = 1.5e5

V_MIN_ST = 2.0

SEGMENT_GLOBS = [
    "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
]

# Agent's training set: first 60 Mach-E sim.csv segments (sorted)
AGENT_PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
AGENT_N_TRAIN = 60


def platform_for(csv_path: str) -> str:
    for plat in PARAMS:
        if f"/segments/{plat}/" in csv_path:
            return plat
    raise ValueError(f"unknown platform in path: {csv_path}")


def linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf, cr, v_min=V_MIN_ST):
    K_us = (m * (l_r * cr - l_f * cf)) / (L ** 2 * cf * cr)
    safe = v >= v_min
    ks = (v / L) * np.tan(delta)
    st = v * delta / (L * (1.0 + K_us * v ** 2))
    return np.where(safe, st, ks)


def compute_v3_for_segment(df: pd.DataFrame, plat: str) -> tuple[np.ndarray, np.ndarray, float]:
    """Return (V3_pred_corr, V3_residual, bias) for a single segment."""
    p = PARAMS[plat]
    v = df["v_mps"].to_numpy(dtype=float)
    delta = df["delta_road_rad"].to_numpy(dtype=float)
    meas = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
    pred = linear_st_yaw_rate(v, delta, p["L"], p["l_f"], p["l_r"], p["m"], p["I_z"], CF, CR)
    err_raw = pred - meas
    straight = np.abs(delta) < 0.01
    bias = float(np.mean(err_raw[straight])) if straight.any() else 0.0
    pred_corr = pred - bias
    err_corr = pred_corr - meas
    return pred_corr, err_corr, bias


def features_for_segment(df: pd.DataFrame) -> np.ndarray:
    t = df["t_s"].to_numpy(dtype=float)
    dt_raw = np.diff(t, prepend=t[0])
    dt = np.where(dt_raw > 0, dt_raw, 0.02)
    delta = df["delta_road_rad"].to_numpy(dtype=float)
    ddelta = np.gradient(delta) / dt
    if "a_y_pred_mps2" in df.columns:
        a_y = df["a_y_pred_mps2"].to_numpy(dtype=float)
    else:
        a_y = np.zeros(len(df))
    v = df["v_mps"].to_numpy(dtype=float)
    X = np.column_stack([v, np.abs(a_y), np.abs(delta), np.sign(ddelta)])
    return X


def main() -> int:
    # Collect canonical segments
    csvs: list[str] = []
    for g in SEGMENT_GLOBS:
        csvs.extend(sorted(glob.glob(str(REPO / g), recursive=True)))
    n_segments = len(csvs)
    print(f"Found {n_segments} canonical segments")

    # Identify agent's 60 training segments: first 60 sorted Mach-E sim.csvs.
    # The agent loaded from MOD/data/sim/segments/FORD_MUSTANG_MACH_E_MK1
    # which is a symlink to data/sim/segments/FORD_MUSTANG_MACH_E_MK1.
    agent_train_root = REPO / "data" / "sim" / "segments" / AGENT_PLATFORM
    agent_train_paths = sorted(agent_train_root.rglob("sim.csv"))[:AGENT_N_TRAIN]
    print(f"Agent training set: {len(agent_train_paths)} Mach-E segments")

    # Step 1: train Ridge once on agent's 60 Mach-E segments.
    X_train_parts = []
    y_train_parts = []
    for p in agent_train_paths:
        df = pd.read_csv(p)
        _, err_corr, _ = compute_v3_for_segment(df, AGENT_PLATFORM)
        X = features_for_segment(df)
        # Drop non-finite rows
        finite = np.isfinite(err_corr) & np.all(np.isfinite(X), axis=1)
        X_train_parts.append(X[finite])
        y_train_parts.append(err_corr[finite])
    X_train = np.vstack(X_train_parts)
    y_train = np.concatenate(y_train_parts)
    print(f"Ridge training data: X={X_train.shape}, y={y_train.shape}")
    ridge = Ridge(alpha=1.0).fit(X_train, y_train)
    print(f"Ridge coefs: {ridge.coef_}, intercept: {ridge.intercept_:.6e}")

    # Step 2: stream over all canonical segments, accumulate SSE.
    agent_sse = 0.0
    base_sse = 0.0
    n_after = 0
    required = {"v_mps", "delta_road_rad", "yaw_rate_meas_rads", "yaw_rate_pred_rads", "t_s"}

    for i, p in enumerate(csvs):
        df = pd.read_csv(p)
        miss = required - set(df.columns)
        if miss:
            raise ValueError(f"missing cols in {p}: {miss}")
        plat = platform_for(p)
        v = df["v_mps"].to_numpy(dtype=float)
        meas = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
        base_pred = df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        v3_pred_corr, _, _ = compute_v3_for_segment(df, plat)
        X = features_for_segment(df)
        oof = ridge.predict(X)
        agent_pred = v3_pred_corr - oof

        keep = (v > 2.0) & np.isfinite(meas) & np.isfinite(agent_pred) & np.isfinite(base_pred)
        agent_sse += float(np.sum((agent_pred[keep] - meas[keep]) ** 2))
        base_sse += float(np.sum((base_pred[keep] - meas[keep]) ** 2))
        n_after += int(keep.sum())

        if (i + 1) % 50 == 0:
            print(f"  processed {i+1}/{n_segments}, n_after={n_after}")

    agent_rmse = float(np.sqrt(agent_sse / n_after))
    base_rmse_recomp = float(np.sqrt(base_sse / n_after))
    improvement_pct = (CANON_BASELINE - agent_rmse) / CANON_BASELINE * 100.0

    print(f"n_segments={n_segments}  n_samples_after_filter={n_after}")
    print(f"baseline (canonical):  {CANON_BASELINE:.10f}")
    print(f"baseline (recomputed): {base_rmse_recomp:.10f}")
    print(f"agent V4 RMSE:         {agent_rmse:.10f}")
    print(f"improvement: {improvement_pct:.4f}%")

    base_match = abs(base_rmse_recomp - CANON_BASELINE) < 1e-6
    notes = [
        "V4 = V3 (Linear single-track, fit C_alpha) with per-segment yaw-gyro bias "
        "(|delta|<0.01 samples) - Ridge residual learner on [v, |a_y|, |delta|, "
        "sign(ddelta)]; Cf=Cr=1.5e5 N/rad (agent's fit_c_alpha stalled at x0 per REPORT).",
        f"Ridge trained ONCE on {len(agent_train_paths)} Mach-E segments (agent's training set), "
        "then applied to all 545 canonical Ford segments. Platform-specific m, I_z, "
        "l_f, l_r, L are used for V3.",
        "Agent's original V4 used LOO across the 60 Mach-E training segments; here we "
        "use a single Ridge fit on all 60 (their 'shipped' model). Applying a Mach-E-trained "
        "residual learner to F-150 Lightning is an out-of-domain extension implicit in "
        "the canonical pooling, but the agent never validated it.",
    ]
    if not base_match:
        notes.append(
            f"baseline recomputation {base_rmse_recomp:.10f} differs from canonical "
            f"{CANON_BASELINE:.10f} by {abs(base_rmse_recomp-CANON_BASELINE):.2e}."
        )
    result = {
        "agent_id": "angleD-m3-agent-04",
        "status": "ok",
        "reason": None,
        "reconstruction_method": "json-coeffs",  # parameters from REPORT + parameters.py + Ridge retrained on agent's training set
        "reconstruction_summary": (
            "V4 = Linear single-track yaw-rate (platform params; Cf=Cr=1.5e5 per agent's "
            "stalled fit) minus per-segment straight-line bias minus a Ridge residual "
            "learner trained on the agent's 60 Mach-E training segments."
        ),
        "n_segments": n_segments,
        "n_samples_after_filter": n_after,
        "baseline_rmse": CANON_BASELINE,
        "baseline_rmse_recomputed": base_rmse_recomp,
        "agent_rmse": agent_rmse,
        "improvement_pct": improvement_pct,
        "notes": " ".join(notes),
    }
    OUT_JSON.write_text(json.dumps(result, indent=2))
    print(f"wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
