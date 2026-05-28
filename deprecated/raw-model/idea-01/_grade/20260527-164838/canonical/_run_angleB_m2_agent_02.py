"""Canonical eval for angleB-m2-agent-02.

Favourite model is V4 from the agent's variant ladder (per REPORT.md and
out/results.txt):
   V4 = first-order steering lag (tau=0.10s) on delta_road_rad, KS kinematics
        (pred = k * v * tan(delta_lag) / L), then per-segment mean-bias removal,
        with k_gain = 1.0277.

Parameters lifted from the agent's tools/analyze.py:
   L = 2.984, DT = 0.02, tau = 0.1, k_gain = 1.0277

Apply across all 545 canonical Ford segments, pool samples with v_mps > 2.0,
compute RMSE vs yaw_rate_meas_rads. Also recompute V0 baseline RMSE
from sim.csv's yaw_rate_pred_rads column as a sanity check.
"""
import glob, json, math, os, sys
import numpy as np
import pandas as pd

REPO_ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI'
GLOBS = [
    f'{REPO_ROOT}/data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv',
    f'{REPO_ROOT}/data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv',
]

# Agent's V4 parameters (verbatim from tools/analyze.py + out/results.txt)
L      = 2.984
DT     = 0.02
TAU    = 0.10
K_GAIN = 1.0277

OUT_PATH = '/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/_grade/20260527-164838/canonical/angleB-m2-agent-02.json'
BASELINE_RMSE_CANONICAL = 0.014740020892723483


def apply_tau(delta, tau, dt=DT):
    if tau <= 0:
        return delta.copy()
    alpha = dt / (tau + dt)
    y = np.empty_like(delta)
    y[0] = delta[0]
    for i in range(1, len(delta)):
        y[i] = y[i-1] + alpha * (delta[i] - y[i-1])
    return y


def main():
    paths = []
    for g in GLOBS:
        paths.extend(glob.glob(g, recursive=True))
    paths = sorted(paths)
    print(f"discovered {len(paths)} segments", file=sys.stderr)

    sse_base = 0.0
    sse_agent = 0.0
    n_samples = 0
    n_segs_used = 0
    n_segs_skipped = 0

    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception as e:
            n_segs_skipped += 1
            continue
        needed = {'v_mps', 'delta_road_rad', 'yaw_rate_meas_rads', 'yaw_rate_pred_rads'}
        if not needed.issubset(df.columns):
            n_segs_skipped += 1
            continue
        if len(df) < 2:
            n_segs_skipped += 1
            continue

        v        = df['v_mps'].to_numpy(dtype=float)
        delta    = df['delta_road_rad'].to_numpy(dtype=float)
        yr_meas  = df['yaw_rate_meas_rads'].to_numpy(dtype=float)
        yr_pred0 = df['yaw_rate_pred_rads'].to_numpy(dtype=float)  # V0

        # Replace any NaNs in delta for the lag filter (just propagate previous)
        # Most segments should be clean; be defensive.
        if not np.isfinite(delta).all():
            # forward-fill NaNs
            d = pd.Series(delta).ffill().bfill().to_numpy(dtype=float)
        else:
            d = delta

        # V4 prediction
        d_lag = apply_tau(d, TAU)
        pred_v4_raw = K_GAIN * v * np.tan(d_lag) / L

        # Per-segment mean bias removal (the agent's V1/V3/V4 step).
        # Bias is computed on the same residual the agent computes:
        #   resid = pred - yr_meas; bias = nanmean(resid)
        # Then pred_corrected = pred - bias.
        # Compute bias using only finite rows.
        resid_v4 = pred_v4_raw - yr_meas
        bias_v4 = np.nanmean(resid_v4) if np.isfinite(resid_v4).any() else 0.0
        if not np.isfinite(bias_v4):
            bias_v4 = 0.0
        pred_v4 = pred_v4_raw - bias_v4

        # Canonical sample filter
        mask = (v > 2.0) & np.isfinite(v) & np.isfinite(yr_meas) & np.isfinite(yr_pred0) & np.isfinite(pred_v4)
        if not mask.any():
            n_segs_skipped += 1
            continue

        e_base = yr_pred0[mask] - yr_meas[mask]
        e_agent = pred_v4[mask] - yr_meas[mask]

        sse_base += float(np.sum(e_base * e_base))
        sse_agent += float(np.sum(e_agent * e_agent))
        n_samples += int(mask.sum())
        n_segs_used += 1

    baseline_rmse_recomputed = math.sqrt(sse_base / n_samples) if n_samples else float('nan')
    agent_rmse = math.sqrt(sse_agent / n_samples) if n_samples else float('nan')
    improvement_pct = (BASELINE_RMSE_CANONICAL - agent_rmse) / BASELINE_RMSE_CANONICAL * 100.0

    notes_parts = []
    notes_parts.append(
        f"Reconstructed V4 = k * v * tan(lag(delta, tau=0.10)) / L with k=1.0277, L=2.984, "
        f"per-segment mean-bias removal — parameters lifted verbatim from agent's tools/analyze.py and out/results.txt; "
        f"no fitted JSON was saved by the agent so coefficients were read out of their source file."
    )
    if abs(baseline_rmse_recomputed - BASELINE_RMSE_CANONICAL) > 1e-6:
        notes_parts.append(
            f"baseline_rmse_recomputed ({baseline_rmse_recomputed:.12f}) differs from canonical cache "
            f"({BASELINE_RMSE_CANONICAL:.12f}) by {baseline_rmse_recomputed-BASELINE_RMSE_CANONICAL:+.2e}."
        )
    notes_parts.append(
        f"Used {n_segs_used} segments ({n_segs_skipped} skipped due to missing columns / empty filter)."
    )
    notes_parts.append(
        "Agent fitted k_gain on first 40 Mach-E segs only — applying it pooled across both Ford platforms "
        "may slightly mis-scale on F-150 segments, but per-segment bias removal compensates for DC offset."
    )

    out = {
        "agent_id": "angleB-m2-agent-02",
        "status": "ok",
        "reason": None,
        "reconstruction_method": "json-coeffs",  # parameters read from agent's source/results
        "reconstruction_summary": (
            "Re-ran the agent's V4 model (KS kinematics with first-order steering lag tau=0.10s "
            "on delta_road_rad, global gain k=1.0277, per-segment mean-bias removal) using the "
            "L, tau, and k_gain values printed in the agent's tools/analyze.py and out/results.txt."
        ),
        "n_segments": n_segs_used,
        "n_samples_after_filter": n_samples,
        "baseline_rmse": BASELINE_RMSE_CANONICAL,
        "baseline_rmse_recomputed": baseline_rmse_recomputed,
        "agent_rmse": agent_rmse,
        "improvement_pct": improvement_pct,
        "notes": " ".join(notes_parts),
    }

    with open(OUT_PATH, 'w') as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
