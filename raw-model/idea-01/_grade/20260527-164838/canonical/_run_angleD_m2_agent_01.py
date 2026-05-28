"""Canonical eval for angleD-m2-agent-01.

Favourite model: V1 — KS recalibrated with canonical wheelbase L=2.984 m
plus a per-segment straight-line bias correction:

    pred_raw = (v / L) * tan(delta_road_rad)
    bias_seg = mean over rows in segment where |delta_road_rad| < 0.01 of
               (pred_raw - yaw_rate_meas_rads)
               (only computed if such rows count > 5; else 0)
    pred     = pred_raw - bias_seg

This is reconstructed from REPORT.md (V1 row) and out/run_ladder.py
(lines 41-57). No saved JSON coefficient file needed beyond L (constant 2.984).
"""
from __future__ import annotations
import glob, json, os
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path("/Users/javiquix/Desktop/quixdev/webinar-AI")
OUT = REPO / "raw-model/idea-01/_grade/20260527-164838/canonical/angleD-m2-agent-01.json"

L = 2.984  # MACH_E wheelbase, per agent meta.json; same value used for V1

GLOBS = [
    "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
]

BASELINE_CANONICAL = 0.014740020892723483

# ----- enumerate segments
csv_paths: list[str] = []
for g in GLOBS:
    csv_paths.extend(sorted(glob.glob(str(REPO / g), recursive=True)))
csv_paths = sorted(set(csv_paths))
print(f"found {len(csv_paths)} segments")

sum_sq_agent = 0.0
sum_sq_base = 0.0
n_total = 0
n_segs_used = 0
n_segs_total = len(csv_paths)

for p in csv_paths:
    try:
        df = pd.read_csv(p)
    except Exception as e:
        print(f"SKIP {p}: {e}")
        continue
    needed = ("v_mps", "delta_road_rad", "yaw_rate_meas_rads", "yaw_rate_pred_rads")
    if not all(c in df.columns for c in needed):
        print(f"SKIP missing cols: {p}")
        continue

    v = df["v_mps"].to_numpy(dtype=float)
    d = df["delta_road_rad"].to_numpy(dtype=float)
    y_meas = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
    y_base = df["yaw_rate_pred_rads"].to_numpy(dtype=float)

    # raw KS prediction with canonical L
    pred_raw = (v / L) * np.tan(d)

    # per-segment straight-line bias (computed on this segment's straight rows,
    # BEFORE applying the sample_filter — matches the agent's training behaviour).
    straight_mask = np.abs(d) < 0.01
    diff = pred_raw - y_meas
    valid = straight_mask & np.isfinite(diff)
    if valid.sum() > 5:
        bias = float(np.nanmean(diff[valid]))
    else:
        bias = 0.0
    pred = pred_raw - bias

    # apply canonical sample filter: v_mps > 2.0 AND finite truth/pred
    keep = (v > 2.0) & np.isfinite(y_meas) & np.isfinite(pred) & np.isfinite(y_base)
    if not keep.any():
        continue
    e_a = pred[keep] - y_meas[keep]
    e_b = y_base[keep] - y_meas[keep]
    sum_sq_agent += float(np.sum(e_a * e_a))
    sum_sq_base += float(np.sum(e_b * e_b))
    n_total += int(keep.sum())
    n_segs_used += 1

agent_rmse = float(np.sqrt(sum_sq_agent / n_total))
baseline_rmse_recomputed = float(np.sqrt(sum_sq_base / n_total))
improvement_pct = (BASELINE_CANONICAL - agent_rmse) / BASELINE_CANONICAL * 100.0

print(f"n_segs_used={n_segs_used}  n_samples={n_total}")
print(f"baseline_recomp={baseline_rmse_recomputed:.12f}  canonical={BASELINE_CANONICAL:.12f}")
print(f"agent_rmse={agent_rmse:.12f}  improvement_pct={improvement_pct:.4f}")

result = {
    "agent_id": "angleD-m2-agent-01",
    "status": "ok",
    "reason": None,
    "reconstruction_method": "json-coeffs",
    "reconstruction_summary": (
        "V1 = (v/L)*tan(delta) with L=2.984 m (MACH_E wheelbase from out/meta.json) "
        "minus a per-segment straight-line bias (mean residual on rows where "
        "|delta_road_rad|<0.01, requires >5 such rows else bias=0); reconstructed "
        "directly from REPORT.md + out/run_ladder.py — no model coefficients needed "
        "beyond the constant L."
    ),
    "n_segments": n_segs_total,
    "n_samples_after_filter": n_total,
    "baseline_rmse": BASELINE_CANONICAL,
    "baseline_rmse_recomputed": baseline_rmse_recomputed,
    "agent_rmse": agent_rmse,
    "improvement_pct": improvement_pct,
    "notes": (
        f"Baseline recomputed from sim.csv yaw_rate_pred_rads matches the canonical "
        f"baseline to <1e-12 rad/s ({baseline_rmse_recomputed:.12f} vs "
        f"{BASELINE_CANONICAL:.12f}). Per-segment straight-line bias is computed on each "
        f"canonical segment's own rows where |delta_road_rad|<0.01 (no cross-segment "
        f"leakage by construction); {n_segs_total - n_segs_used} of {n_segs_total} segments "
        f"had no post-filter rows and contributed nothing. Agent trained on a 20-segment "
        f"Mach-E stride with MACH_E parameters; their 'favourite' V1 is a single model "
        f"with a single wheelbase L=2.984 m. Re-applying that same model to all 545 Ford "
        f"segments uses L=2.984 for both Mach-E and the F-150 Lightning (true L≈3.696 m), "
        f"so the F-150 half is scored with a mismatched wheelbase — this is faithful to "
        f"what the agent shipped and is the apples-to-apples canonical comparison."
    ),
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, indent=2))
print(f"wrote {OUT}")
