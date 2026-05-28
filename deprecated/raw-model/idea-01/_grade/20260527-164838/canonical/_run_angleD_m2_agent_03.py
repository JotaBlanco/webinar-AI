"""Canonical eval for angleD-m2-agent-03.

Favourite model: V1 — canonical-L KS yaw rate (v/L)*tan(delta) + per-segment
yaw-gyro bias subtraction on straight-line samples (|delta_road| < 0.01 rad),
requiring >50 such samples to apply the bias (else 0.0).

Since the sim.csv's stock `yaw_rate_pred_rads` already equals (v/L)*tan(delta)
with each platform's canonical L (per report's hand-check, RMSE diff ~1e-7), we
use it directly as the KS base. The agent's V1 code is platform-agnostic in
structure — it computes ks_pred from L for whichever platform's segments it
loads — so applying that same recipe across both Ford platforms (each with its
own L) is the faithful generalisation to the canonical eval set.
"""
from __future__ import annotations
import glob, json, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI")
SEG_GLOBS = [
    "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
]
SAMPLE_FILTER_V = 2.0
TRUTH = "yaw_rate_meas_rads"

# accumulators for pooled RMSE
agent_sse = 0.0
base_sse = 0.0
n_samples = 0
n_segments = 0
n_segments_with_bias = 0

paths = []
for g in SEG_GLOBS:
    paths.extend(sorted((ROOT).glob(g)))
paths = sorted(set(paths))
print(f"Found {len(paths)} segments")

for p in paths:
    df = pd.read_csv(p)
    if TRUTH not in df.columns or "yaw_rate_pred_rads" not in df.columns:
        continue
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    meas = df[TRUTH].to_numpy()
    ks_pred = df["yaw_rate_pred_rads"].to_numpy()  # = (v/L)*tan(delta), per report
    # per-segment bias on straights with v_mps > 2.0 — agent's V1 didn't apply
    # the v>2 filter for bias estimation, but the same v>2 filter is applied for
    # scoring; we use the agent's V1 bias recipe verbatim (no v filter on the
    # straight mask) since changing it would not be the agent's model.
    straight_mask = np.abs(delta) < 0.01
    if straight_mask.sum() > 50:
        bias = float(np.mean(ks_pred[straight_mask] - meas[straight_mask]))
        n_segments_with_bias += 1
    else:
        bias = 0.0
    agent_pred = ks_pred - bias

    # apply canonical sample filter
    keep = v > SAMPLE_FILTER_V
    if not keep.any():
        n_segments += 1
        continue
    err_agent = agent_pred[keep] - meas[keep]
    err_base = ks_pred[keep] - meas[keep]
    agent_sse += float(np.sum(err_agent * err_agent))
    base_sse += float(np.sum(err_base * err_base))
    n_samples += int(keep.sum())
    n_segments += 1

agent_rmse = math.sqrt(agent_sse / n_samples)
base_rmse_recomputed = math.sqrt(base_sse / n_samples)
canonical_baseline = 0.014740020892723483
improvement_pct = (canonical_baseline - agent_rmse) / canonical_baseline * 100.0

result = {
    "agent_id": "angleD-m2-agent-03",
    "status": "ok",
    "reason": None,
    "reconstruction_method": "json-coeffs",
    "reconstruction_summary": (
        "Re-ran agent's V1 (their declared best variant): use sim.csv's stock "
        "yaw_rate_pred_rads as KS base (= (v/L)*tan(delta) with each platform's "
        "canonical wheelbase per the report's hand-check), then subtract a "
        "per-segment yaw-gyro bias estimated as mean(ks_pred - meas) on samples "
        "with |delta_road|<0.01 rad, requiring >50 such samples per segment."
    ),
    "n_segments": n_segments,
    "n_samples_after_filter": n_samples,
    "baseline_rmse": canonical_baseline,
    "baseline_rmse_recomputed": base_rmse_recomputed,
    "agent_rmse": agent_rmse,
    "improvement_pct": improvement_pct,
    "notes": (
        f"V1 declared best in REPORT.md table: 'V1 — KS w/ canonical L + "
        f"per-segment yaw-gyro bias on straights ... only variant that helps'. "
        f"Bias applied to {n_segments_with_bias}/{n_segments} segments (others "
        f"lacked >50 straight samples and used bias=0). Recipe is platform-"
        f"agnostic (per-segment offset), so it generalises naturally from the "
        f"agent's Mach-E-only scoring to the full Ford canonical set."
    ),
}

out_path = ROOT / "raw-model/idea-01/_grade/20260527-164838/canonical/angleD-m2-agent-03.json"
out_path.write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
