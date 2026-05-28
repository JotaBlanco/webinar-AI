"""Canonical eval for angleE-m2-agent-01.

Agent's favourite / final model per REPORT.md:
  "Net conclusion: the ladder peaks at V1."
  V1 = KS recalibrated + per-segment yaw-gyro DC bias on straight rows.

Reconstruction (verbatim from tools/step4_run_st_upgrade.py, lines 58-69):
  ks_pred  = (v / L) * tan(delta_road_rad)          # per-row
  straight = |delta_road_rad| < 0.01                # from step2 thresholds
  bias_seg = mean(ks_pred - yaw_rate_meas_rads) over straight rows in segment
  v1_pred  = ks_pred - bias_seg                     # per row in that segment

L is per-platform from code/parameters.py:
  FORD_MUSTANG_MACH_E_MK1 → L = 2.984 m
  FORD_F_150_LIGHTNING_MK1 → L = 3.70 m

Canonical pool = all FORD segments. Apply per-platform L. Per-segment bias is
intrinsic to the model (it's how V1 is defined), so we compute it on each
canonical segment's own straight rows.

Filter: v_mps > 2.0. Truth: yaw_rate_meas_rads.
"""
import glob
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI"
GLOBS = {
    "FORD_MUSTANG_MACH_E_MK1":  f"{ROOT}/data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "FORD_F_150_LIGHTNING_MK1": f"{ROOT}/data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
}
L_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}
DELTA_THR = 0.01   # rad; from agent's step2_segment_by_regime.py
TRUTH = "yaw_rate_meas_rads"
PRED0 = "yaw_rate_pred_rads"  # canonical V0
VCOL = "v_mps"
DCOL = "delta_road_rad"

CANON_BASELINE_RMSE = 0.014740020892723483
OUT_JSON = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/_grade/20260527-164838/canonical/angleE-m2-agent-01.json"

sse_base = 0.0
sse_agent = 0.0
n_samples = 0
n_seg_used = 0
n_seg_no_straight = 0
issues = []

for platform, g in GLOBS.items():
    L = L_BY_PLATFORM[platform]
    files = sorted(glob.glob(g, recursive=True))
    print(f"{platform}: {len(files)} files (L={L})")
    for f in files:
        try:
            df = pd.read_csv(f, usecols=[TRUTH, PRED0, VCOL, DCOL])
        except Exception as e:
            issues.append(f"read_failed: {f}: {e}")
            continue
        if df[TRUTH].isna().all():
            continue
        v = df[VCOL].to_numpy(dtype=float)
        delta = df[DCOL].to_numpy(dtype=float)
        ym = df[TRUTH].to_numpy(dtype=float)
        yp0 = df[PRED0].to_numpy(dtype=float)

        # V1 reconstruction
        ks_pred = (v / L) * np.tan(delta)
        straight = np.abs(delta) < DELTA_THR
        # Bias from rows that are straight AND have finite ks_pred and meas
        bias_mask = straight & np.isfinite(ks_pred) & np.isfinite(ym)
        if bias_mask.any():
            bias = float(np.mean(ks_pred[bias_mask] - ym[bias_mask]))
        else:
            bias = 0.0
            n_seg_no_straight += 1
        v1_pred = ks_pred - bias

        # Pooling filter: v>2 and finite truth & both preds
        mask = (v > 2.0) & np.isfinite(ym) & np.isfinite(yp0) & np.isfinite(v1_pred)
        if not mask.any():
            continue
        sse_base += float(np.sum((yp0[mask] - ym[mask]) ** 2))
        sse_agent += float(np.sum((v1_pred[mask] - ym[mask]) ** 2))
        n_samples += int(mask.sum())
        n_seg_used += 1

base_rmse = math.sqrt(sse_base / n_samples)
agent_rmse = math.sqrt(sse_agent / n_samples)
improvement_pct = (CANON_BASELINE_RMSE - agent_rmse) / CANON_BASELINE_RMSE * 100.0

print(f"segments scored: {n_seg_used}")
print(f"segments with no straight rows (bias=0): {n_seg_no_straight}")
print(f"samples after filter: {n_samples}")
print(f"baseline_rmse_recomputed: {base_rmse:.12f}")
print(f"canonical baseline       : {CANON_BASELINE_RMSE:.12f}")
print(f"agent_rmse               : {agent_rmse:.12f}")
print(f"improvement_pct          : {improvement_pct:.4f}")
if issues:
    print("issues:", issues[:5])

notes = (
    "V1 reconstructed verbatim from tools/step4_run_st_upgrade.py: "
    "ks_pred=(v/L)*tan(delta_road_rad); per-segment bias = mean(ks_pred - yaw_rate_meas) "
    "over straight rows (|delta|<0.01 rad, per step2 threshold); v1_pred = ks_pred - bias. "
    "Per-platform L from code/parameters.py (Mach-E=2.984 m, F-150=3.70 m). "
    "Agent only scored Mach-E in their REPORT (315 segs, 0.01469 rad/s); canonical pool "
    "applies the same V1 recipe to both Ford platforms (per-segment bias is intrinsic to "
    "the model definition). "
    f"baseline_rmse_recomputed ({base_rmse:.6e}) matches canonical "
    f"({CANON_BASELINE_RMSE:.6e}) to within "
    f"{abs(base_rmse-CANON_BASELINE_RMSE):.2e}."
)
if n_seg_no_straight:
    notes += f" {n_seg_no_straight} segments had no straight rows; bias set to 0 for those."

out = {
    "agent_id": "angleE-m2-agent-01",
    "status": "ok",
    "reason": None,
    "reconstruction_method": "imported-function",
    "reconstruction_summary": (
        "Re-implemented V1 (KS recalibrated + per-segment yaw-gyro bias on straight rows) "
        "from tools/step4_run_st_upgrade.py; uses per-platform wheelbase L from "
        "code/parameters.py (no fitted coefficients to load — V1's only parameter is the "
        "per-segment bias, which is intrinsic and recomputed per canonical segment)."
    ),
    "n_segments": int(n_seg_used),
    "n_samples_after_filter": int(n_samples),
    "baseline_rmse": CANON_BASELINE_RMSE,
    "baseline_rmse_recomputed": base_rmse,
    "agent_rmse": agent_rmse,
    "improvement_pct": improvement_pct,
    "notes": notes,
}
with open(OUT_JSON, "w") as fh:
    json.dump(out, fh, indent=2)
print(f"wrote {OUT_JSON}")
