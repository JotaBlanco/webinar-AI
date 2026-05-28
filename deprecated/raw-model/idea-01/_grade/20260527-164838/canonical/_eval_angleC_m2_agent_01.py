"""Canonical eval for angleC-m2-agent-01 (V3 generalising per-platform model).

Per the agent's REPORT:
  Headline = "V2+V3" generalising per-platform fit, 0.924 -> 0.892 deg/s.
V3 is the most-evolved generalising model and = V1 bias + V2 gain + V3 lag,
all per-platform. Parameters come from out/results.json (fit on
FORD_MUSTANG_MACH_E_MK1):
    b1   = 0.0007538650000000003
    k2   = 1.0686794838837996
    shift= +1 sample

Prediction equation (applied per-segment to yaw_rate_pred_rads):
    yp1 = yp0 - b1
    yp2 = k2 * yp1
    yp3 = shift_arr(yp2, +1)  # delay by 1 sample; sample 0 becomes NaN

Canonical eval pools both Ford platforms; we apply the same Mustang-fit
parameters to all 545 segments (the canonical contract scores the parameter
set the agent shipped against the full Ford pool).

Filter: v_mps > 2.0; samples with NaN due to lag-shift are also dropped
(they cannot be scored).
"""
import glob, json, math, os, sys
from datetime import datetime
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI"
GLOBS = [
    f"{ROOT}/data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    f"{ROOT}/data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
]
TRUTH = "yaw_rate_meas_rads"
PRED0 = "yaw_rate_pred_rads"
VCOL = "v_mps"

B1 = 0.0007538650000000003
K2 = 1.0686794838837996
SHIFT = 1  # +1 sample delay (yp3[1:] = yp2[:-1])

# Canonical baseline (for sanity-check)
CANON_BASELINE_RMSE = 0.014740020892723483

OUT_JSON = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/_grade/20260527-164838/canonical/angleC-m2-agent-01.json"

def shift_arr(a, s):
    out = np.full_like(a, np.nan)
    if s == 0:
        out[:] = a
    elif s > 0:
        out[s:] = a[:-s]
    else:
        out[:s] = a[-s:]
    return out

files = []
for g in GLOBS:
    files.extend(sorted(glob.glob(g, recursive=True)))
files = sorted(set(files))
print(f"Found {len(files)} candidate sim.csv files")

n_seg_used = 0
sse_base = 0.0
sse_agent = 0.0
n_samples = 0
issues = []

for f in files:
    try:
        df = pd.read_csv(f, usecols=[TRUTH, PRED0, VCOL])
    except Exception as e:
        issues.append(f"read_failed: {f}: {e}")
        continue
    if TRUTH not in df.columns or PRED0 not in df.columns or VCOL not in df.columns:
        issues.append(f"missing_cols: {f}")
        continue
    if df[TRUTH].isna().all():
        # No truth -> can't score; skip silently
        continue

    yp0 = df[PRED0].to_numpy(dtype=float)
    ym = df[TRUTH].to_numpy(dtype=float)
    v = df[VCOL].to_numpy(dtype=float)

    # Reconstruct agent V3 prediction
    yp1 = yp0 - B1
    yp2 = K2 * yp1
    yp3 = shift_arr(yp2, SHIFT)

    # Mask: v>2 AND truth not nan AND baseline pred not nan AND agent pred not nan
    mask = (v > 2.0) & (~np.isnan(ym)) & (~np.isnan(yp0)) & (~np.isnan(yp3))
    if not mask.any():
        continue

    res_base = yp0[mask] - ym[mask]
    res_agent = yp3[mask] - ym[mask]

    sse_base += float(np.sum(res_base ** 2))
    sse_agent += float(np.sum(res_agent ** 2))
    n_samples += int(mask.sum())
    n_seg_used += 1

base_rmse = math.sqrt(sse_base / n_samples)
agent_rmse = math.sqrt(sse_agent / n_samples)
improvement_pct = (CANON_BASELINE_RMSE - agent_rmse) / CANON_BASELINE_RMSE * 100.0

print(f"segments scored: {n_seg_used}")
print(f"samples after filter: {n_samples}")
print(f"baseline rmse recomputed: {base_rmse:.12f}")
print(f"canonical baseline rmse : {CANON_BASELINE_RMSE:.12f}")
print(f"agent rmse              : {agent_rmse:.12f}")
print(f"improvement pct         : {improvement_pct:.4f}")
if issues:
    print("issues:", issues[:5], "...")

notes_parts = []
# Compare recomputed baseline against canonical.
# Note: canonical baseline is over 1,364,925 samples (all v>2 samples across 545 segs).
# Our recomputed baseline drops 1 sample per segment because the +1 lag-shift
# masks sample-0 of every segment as NaN for the AGENT prediction; but for
# baseline_rmse_recomputed we use the SAME mask (so both rmses are over the
# same n_samples).  Therefore baseline_rmse_recomputed is over (1,364,925 - dropped)
# samples, where dropped = sum over segments of (sample-0 if it qualifies for v>2).
dropped = 1364925 - n_samples
notes_parts.append(
    f"Reconstructed V3 = shift(+1 sample, k*(yp0 - b1)) with "
    f"b1={B1}, k={K2}, shift=+1; parameters from out/results.json, "
    f"fit on FORD_MUSTANG_MACH_E_MK1 only. Applied identical params across both "
    f"Ford platforms in the canonical pool."
)
notes_parts.append(
    f"baseline_rmse_recomputed (={base_rmse:.6e}) is scored on the same "
    f"{n_samples} samples as the agent (the +1-sample lag drops {dropped} "
    f"segment-leading samples vs the canonical {1364925}); the canonical "
    f"baseline {CANON_BASELINE_RMSE:.6e} is over all 1,364,925 samples and is "
    f"therefore not bit-identical -- difference is due to the lag-induced sample drop, "
    f"not a recomputation discrepancy."
)
notes_parts.append(
    "Agent labels V4 (per-segment bias) as calibration not model improvement (rule 8); "
    "we score the V3 generalising model per their own headline declaration."
)

out = {
    "agent_id": "angleC-m2-agent-01",
    "status": "ok",
    "reason": None,
    "reconstruction_method": "json-coeffs",
    "reconstruction_summary": (
        "Reconstructed agent's V3 generalising per-platform model "
        "(yp = shift(+1, k*(yp0 - b1))) using b1=0.000753865, k=1.068679, shift=+1 "
        "from out/results.json."
    ),
    "n_segments": int(n_seg_used),
    "n_samples_after_filter": int(n_samples),
    "baseline_rmse": CANON_BASELINE_RMSE,
    "baseline_rmse_recomputed": base_rmse,
    "agent_rmse": agent_rmse,
    "improvement_pct": improvement_pct,
    "notes": " ".join(notes_parts),
}

with open(OUT_JSON, "w") as fh:
    json.dump(out, fh, indent=2)
print(f"wrote {OUT_JSON}")
