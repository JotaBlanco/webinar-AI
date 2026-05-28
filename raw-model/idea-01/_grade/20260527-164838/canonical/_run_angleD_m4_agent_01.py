"""Canonical eval — angleD-m4-agent-01 favourite model is V1.

V1 = KS yaw-rate using Mach-E wheelbase L=2.984 minus a per-segment
straight-line bias (mean residual where |delta_road_rad| < 0.01).
Per-segment bias generalises naturally to any sim.csv.
"""
from __future__ import annotations
import glob, json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI")
OUT = ROOT / "raw-model/idea-01/_grade/20260527-164838/canonical/angleD-m4-agent-01.json"

# Mach-E wheelbase — the L the agent's V1 used.
L_MACHE = 2.984

GLOBS = [
    "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
]
SAMPLE_FILTER_V_MIN = 2.0
TRUTH = "yaw_rate_meas_rads"
BASELINE_PRED = "yaw_rate_pred_rads"
STRAIGHT_DELTA = 0.01

paths: list[str] = []
for g in GLOBS:
    paths.extend(sorted(glob.glob(str(ROOT / g), recursive=True)))

n_seg = len(paths)

sse_agent = 0.0
sse_base = 0.0
n_samples = 0

for p in paths:
    df = pd.read_csv(p)
    v = df["v_mps"].to_numpy(dtype=float)
    d = df["delta_road_rad"].to_numpy(dtype=float)
    meas = df[TRUTH].to_numpy(dtype=float)
    base_pred = df[BASELINE_PRED].to_numpy(dtype=float)

    # KS yaw rate using Mach-E L
    psi_dot_ks = (v / L_MACHE) * np.tan(d)
    raw_resid = psi_dot_ks - meas
    # per-segment bias from straight-line samples
    sl_mask = np.abs(d) < STRAIGHT_DELTA
    if sl_mask.any():
        # match agent's code which does not exclude NaNs explicitly but uses pandas mean
        bias = float(np.nanmean(raw_resid[sl_mask]))
        if not math.isfinite(bias):
            bias = 0.0
    else:
        bias = 0.0
    pred_v1 = psi_dot_ks - bias

    # apply canonical sample filter
    mask = v > SAMPLE_FILTER_V_MIN
    # also require finite values across all needed
    finite = np.isfinite(pred_v1) & np.isfinite(meas) & np.isfinite(base_pred)
    mask = mask & finite
    if not mask.any():
        continue
    e_agent = pred_v1[mask] - meas[mask]
    e_base = base_pred[mask] - meas[mask]
    sse_agent += float(np.sum(e_agent * e_agent))
    sse_base += float(np.sum(e_base * e_base))
    n_samples += int(mask.sum())

agent_rmse = math.sqrt(sse_agent / n_samples)
base_rmse_recomp = math.sqrt(sse_base / n_samples)
canonical_baseline = 0.014740020892723483
improvement_pct = (canonical_baseline - agent_rmse) / canonical_baseline * 100.0

result = {
    "agent_id": "angleD-m4-agent-01",
    "status": "ok",
    "reason": None,
    "reconstruction_method": "json-coeffs",
    "reconstruction_summary": (
        "Re-ran agent's V1 (declared 'best, ship' in REPORT): KS yaw-rate "
        "psi_dot=(v/L)*tan(delta) with L=2.984 (Mach-E wheelbase per "
        "code/parameters.py PARAM_BY_PLATFORM) minus a per-segment bias = "
        "mean residual on straight-line samples (|delta|<0.01)."
    ),
    "n_segments": n_seg,
    "n_samples_after_filter": n_samples,
    "baseline_rmse": canonical_baseline,
    "baseline_rmse_recomputed": base_rmse_recomp,
    "agent_rmse": agent_rmse,
    "improvement_pct": improvement_pct,
    "notes": (
        "Agent V1 procedure (KS + per-segment straight-line bias removal) is "
        "platform-agnostic at evaluation time: the only fixed parameter is L. "
        "Agent fit and reported on 12 Mach-E segments only; here we extend the "
        "same procedure (with agent's Mach-E L=2.984) across all 545 canonical "
        "Ford segments including 230 F-150 Lightning segments (true L=3.70), "
        "so Lightning predictions use the wrong wheelbase by agent's own "
        "platform choice. Per-segment bias is recomputed per segment from its "
        "own straight-line samples (agent's exact recipe)."
    ),
}

OUT.write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
