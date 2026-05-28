"""Canonical eval for angleB-m3-agent-05.

Favourite model = V1 from agent's ladder: V0 (sim.csv `yaw_rate_pred_rads`) minus
per-segment mean residual on straight samples (|delta_road| < 0.01), constrained
to the canonical sample filter (v_mps > 2.0).

Apply across all 545 canonical Ford segments. Pool samples where v_mps > 2.0.
"""
from __future__ import annotations
import glob
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI")
GLOBS = [
    "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
]
OUT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/_grade/20260527-164838/canonical/angleB-m3-agent-05.json")
CANONICAL_V0 = 0.014740020892723483

paths = []
for g in GLOBS:
    paths.extend(sorted(glob.glob(str(ROOT / g), recursive=True)))
paths = sorted(set(paths))

sq_err_base = 0.0
sq_err_agent = 0.0
n_samples = 0
n_segments = 0
n_segments_with_samples = 0

NEEDED = {"v_mps", "delta_road_rad", "yaw_rate_meas_rads", "yaw_rate_pred_rads"}

for p in paths:
    try:
        df = pd.read_csv(p)
    except Exception:
        continue
    if not NEEDED.issubset(df.columns):
        continue
    n_segments += 1
    v = df["v_mps"].to_numpy()
    d = df["delta_road_rad"].to_numpy()
    ym = df["yaw_rate_meas_rads"].to_numpy()
    yp = df["yaw_rate_pred_rads"].to_numpy()

    # canonical sample filter
    valid = v > 2.0
    # finite check
    finite = np.isfinite(v) & np.isfinite(d) & np.isfinite(ym) & np.isfinite(yp)
    valid &= finite

    # per-segment bias from straight samples within valid filter
    straight = np.abs(d) < 0.01
    mask_str = straight & valid
    if mask_str.any():
        bias = float(np.mean((yp - ym)[mask_str]))
    else:
        bias = 0.0

    agent_pred = yp - bias

    if not valid.any():
        continue

    diff_base = yp[valid] - ym[valid]
    diff_agent = agent_pred[valid] - ym[valid]
    sq_err_base += float(np.sum(diff_base ** 2))
    sq_err_agent += float(np.sum(diff_agent ** 2))
    n_samples += int(valid.sum())
    n_segments_with_samples += 1

baseline_rmse_recomputed = float(np.sqrt(sq_err_base / n_samples))
agent_rmse = float(np.sqrt(sq_err_agent / n_samples))
improvement_pct = (CANONICAL_V0 - agent_rmse) / CANONICAL_V0 * 100.0

notes_parts = []
if abs(baseline_rmse_recomputed - CANONICAL_V0) > 1e-6:
    notes_parts.append(
        f"baseline sanity-check drift: recomputed {baseline_rmse_recomputed:.12f} vs canonical {CANONICAL_V0:.12f}"
    )
notes_parts.append(
    "Reconstructed agent's favourite V1 = V0 (CSV yaw_rate_pred_rads) minus per-segment mean residual on straight samples (|delta_road|<0.01, v>2.0). "
    f"Agent originally scored Mach-E only (306 segs); extended to all {n_segments} canonical Ford segments ({n_segments_with_samples} contained samples after v>2.0 filter). "
    "Bias correction is per-segment (1 DOF/seg) computed in-script from straight samples in each segment; no fitted parameters file required. "
    "Segments lacking straight samples fall back to bias=0 (i.e. V0)."
)
notes = " ".join(notes_parts)

result = {
    "agent_id": "angleB-m3-agent-05",
    "status": "ok",
    "reason": None,
    "reconstruction_method": "imported-function",
    "reconstruction_summary": "Re-ran agent's V1 (their declared best): V0 yaw_rate_pred_rads minus per-segment mean residual on straight samples (|delta_road|<0.01) within v>2.0, reproducing the run_ladder.py V1 branch.",
    "n_segments": n_segments,
    "n_samples_after_filter": n_samples,
    "baseline_rmse": CANONICAL_V0,
    "baseline_rmse_recomputed": baseline_rmse_recomputed,
    "agent_rmse": agent_rmse,
    "improvement_pct": improvement_pct,
    "notes": notes,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
