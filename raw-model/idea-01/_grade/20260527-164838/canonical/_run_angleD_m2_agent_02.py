"""Canonical eval for angleD-m2-agent-02.

Agent's favourite model: V1 = KS yaw rate (psi_dot = (v/L) * tan(delta))
with per-segment straight-line gyro bias removal (bias = mean of
(pred - meas) on samples with |delta_road_rad| < 0.01; subtracted from
that segment's predictions).

Per-platform wheelbase L:
  FORD_MUSTANG_MACH_E_MK1 -> 2.984 m
  FORD_F_150_LIGHTNING_MK1 -> 3.70 m

Sample filter for pooled RMSE: v_mps > 2.0
Truth channel: yaw_rate_meas_rads
"""
from __future__ import annotations
import glob, json, math
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path("/Users/javiquix/Desktop/quixdev/webinar-AI")
OUT_JSON = REPO / "raw-model/idea-01/_grade/20260527-164838/canonical/angleD-m2-agent-02.json"

PLATFORM_L = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}

GLOBS = [
    "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
]

def platform_of(p: str) -> str:
    for key in PLATFORM_L:
        if f"/segments/{key}/" in p:
            return key
    raise ValueError(p)

paths: list[str] = []
for g in GLOBS:
    paths.extend(sorted(glob.glob(str(REPO / g), recursive=True)))
paths = sorted(set(paths))

n_segments = len(paths)
print(f"segments: {n_segments}")

sq_err_base = 0.0
sq_err_agent = 0.0
n_samples = 0

for p in paths:
    plat = platform_of(p)
    L = PLATFORM_L[plat]
    df = pd.read_csv(p)
    v = df["v_mps"].to_numpy(dtype=float)
    delta = df["delta_road_rad"].to_numpy(dtype=float)
    meas = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
    base = df["yaw_rate_pred_rads"].to_numpy(dtype=float)

    # V1 KS prediction
    pred = (v / L) * np.tan(delta)

    # Per-segment straight-line bias: mean of (pred - meas) for |delta| < 0.01,
    # computed over the WHOLE segment (matching the agent's loop which did NOT
    # apply the sample_filter before computing bias).
    straight = np.abs(delta) < 0.01
    if straight.any():
        bias = float(np.mean(pred[straight] - meas[straight]))
    else:
        bias = 0.0
    pred_corrected = pred - bias

    # Apply sample filter for pooled RMSE
    keep = v > 2.0
    if not keep.any():
        continue
    m = meas[keep]
    sq_err_base += float(np.sum((base[keep] - m) ** 2))
    sq_err_agent += float(np.sum((pred_corrected[keep] - m) ** 2))
    n_samples += int(keep.sum())

baseline_rmse_recomputed = math.sqrt(sq_err_base / n_samples)
agent_rmse = math.sqrt(sq_err_agent / n_samples)
baseline_rmse = 0.014740020892723483
improvement_pct = (baseline_rmse - agent_rmse) / baseline_rmse * 100.0

print(f"n_samples={n_samples}")
print(f"baseline_recomp={baseline_rmse_recomputed:.12f}")
print(f"agent_rmse     ={agent_rmse:.12f}")
print(f"improvement_pct={improvement_pct:.4f}")

notes_parts = []
diff = abs(baseline_rmse_recomputed - baseline_rmse)
if diff > 1e-6:
    notes_parts.append(f"baseline recomputation differs from cached by {diff:.3e}")
notes_parts.append(
    "V1 applies per-segment straight-line yaw-gyro bias (mean of pred-meas where "
    "|delta_road|<0.01) — fitted in-sample on each canonical segment, matching "
    "the agent's loop. Wheelbase L is per-platform (Mach-E 2.984 m, Lightning "
    "3.70 m). The agent originally fit V1 on 25 Mach-E segments; here it is "
    "applied to all 545 Ford segments (both platforms)."
)
notes = " ".join(notes_parts)

result = {
    "agent_id": "angleD-m2-agent-02",
    "status": "ok",
    "reason": None,
    "reconstruction_method": "imported-function",
    "reconstruction_summary": (
        "Re-implemented agent's V1: stock KS yaw-rate (v/L)*tan(delta) with "
        "per-segment straight-line bias removal (mean residual where "
        "|delta_road|<0.01), using each platform's openpilot-canonical wheelbase L."
    ),
    "n_segments": n_segments,
    "n_samples_after_filter": n_samples,
    "baseline_rmse": baseline_rmse,
    "baseline_rmse_recomputed": baseline_rmse_recomputed,
    "agent_rmse": agent_rmse,
    "improvement_pct": improvement_pct,
    "notes": notes,
}

OUT_JSON.write_text(json.dumps(result, indent=2))
print(f"wrote {OUT_JSON}")
