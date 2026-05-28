"""Canonical eval for angleD-m4-agent-05.

Favourite model (from REPORT.md):
    > "Best variant. V2 — picked on overall RMSE; written to out/best_V2.csv"

V2 = Linear single-track yaw-rate with PRIOR (platform-canonical) Cα
     plus a per-segment straight-line bias correction (computed on |delta|<0.01
     samples of each segment, requiring >50 such rows else bias=0).

Reconstruction:
  - Reused the agent's own equation from
    skills/lateral-fidelity-triage/triage.py::linear_st_yaw_rate :
        K_us = m·(l_r·Cαr − l_f·Cαf) / (L²·Cαf·Cαr)
        ψ̇   = v·δ / (L·(1 + K_us·v²))           if v >= 2.0
        ψ̇   = (v/L)·tan(δ)                      otherwise (KS fallback)
  - Reused the agent's per_segment_bias logic from tools/run_ladder.py:
        bias = mean( pred_raw - meas )  on |delta|<0.01 rows (per-segment),
               only applied if >50 such rows; else bias = 0.
  - Parameters loaded from agent's code/parameters.py via PARAM_BY_PLATFORM:
        FORD_MUSTANG_MACH_E_MK1: L=2.984, l_f=1.313, l_r=1.671, m=2336,
            I_z=4879.05, Cαf=286551, Cαr=355912
        FORD_F_150_LIGHTNING_MK1: L=3.70,  l_f=1.628, l_r=2.072, m=3084,
            I_z=9903.37, Cαf=378307, Cαr=469878
  - No fitted JSON coefficients — the only learned per-segment quantity is the
    DC bias, which is recomputed per canonical segment exactly as the agent did.
"""
from __future__ import annotations
import glob
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path("/Users/javiquix/Desktop/quixdev/webinar-AI")
AGENT = REPO / "webinar-angle-D/module-4/agent-05"
OUT = REPO / "raw-model/idea-01/_grade/20260527-164838/canonical/angleD-m4-agent-05.json"

sys.path.insert(0, str(AGENT / "code"))
from parameters import PARAM_BY_PLATFORM  # noqa: E402

BASELINE_CANONICAL = 0.014740020892723483
V_MIN_ST = 2.0

GLOBS = [
    "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
]

PLATFORMS = ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1")


def detect_platform(path: str) -> str:
    for p in PLATFORMS:
        if f"/{p}/" in path:
            return p
    raise ValueError(f"unknown platform in {path}")


def linear_st_yaw_rate(v: np.ndarray, d: np.ndarray, pp) -> np.ndarray:
    L, l_f, l_r = pp.L, pp.l_f, pp.l_r
    m, I_z = pp.m, pp.I_z
    Cf, Cr = pp.C_alpha_f, pp.C_alpha_r
    K_us = (m * (l_r * Cr - l_f * Cf)) / (L ** 2 * Cf * Cr)
    safe = v >= V_MIN_ST
    st = v * d / (L * (1.0 + K_us * v ** 2))
    ks = (v / L) * np.tan(d)
    return np.where(safe, st, ks)


def per_segment_bias_v2(pred_raw: np.ndarray, meas: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Replicates tools/run_ladder.py::per_segment_bias for a single segment.
    The agent's function loops over __source__ groups; called per-segment here it
    operates on the whole segment as one group."""
    straight = np.abs(d) < 0.01
    valid = straight & np.isfinite(pred_raw - meas)
    if valid.sum() > 50:
        bias = float(np.nanmean(pred_raw[valid] - meas[valid]))
    else:
        bias = 0.0
    return pred_raw - bias


# enumerate segments
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

for path in csv_paths:
    try:
        df = pd.read_csv(path)
    except Exception as e:
        print(f"SKIP read fail {path}: {e}")
        continue
    needed = ("v_mps", "delta_road_rad", "yaw_rate_meas_rads", "yaw_rate_pred_rads")
    if not all(c in df.columns for c in needed):
        print(f"SKIP missing cols: {path}")
        continue

    pp = PARAM_BY_PLATFORM[detect_platform(path)]
    v = df["v_mps"].to_numpy(dtype=float)
    d = df["delta_road_rad"].to_numpy(dtype=float)
    y_meas = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
    y_base = df["yaw_rate_pred_rads"].to_numpy(dtype=float)

    pred_raw = linear_st_yaw_rate(v, d, pp)
    pred = per_segment_bias_v2(pred_raw, y_meas, d)

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

print(f"n_segs_used={n_segs_used}/{n_segs_total}  n_samples={n_total}")
print(f"baseline_recomp={baseline_rmse_recomputed:.12f}  canonical={BASELINE_CANONICAL:.12f}")
print(f"agent_rmse={agent_rmse:.12f}  improvement_pct={improvement_pct:.4f}")

base_sanity_ok = abs(baseline_rmse_recomputed - BASELINE_CANONICAL) < 1e-6
notes_parts = [
    "V2 reconstructed by importing PARAM_BY_PLATFORM and re-implementing the "
    "two-line linear-ST gain + per-segment straight-line bias verbatim from "
    "skills/lateral-fidelity-triage/triage.py and tools/run_ladder.py. ",
    "Agent's training set was 8 Mach-E segments only; per-segment bias is "
    "recomputed on each canonical segment's own straight-line rows (no "
    "cross-segment leakage), so the recipe ports cleanly to both Ford "
    "platforms with their respective canonical Cα/L/m/I_z. ",
    "Platform-specific params used: MACH_E (L=2.984, Cαf=286551, Cαr=355912) "
    "and F-150 LIGHTNING (L=3.70, Cαf=378307, Cαr=469878). ",
    f"Baseline sanity-check {'matches' if base_sanity_ok else 'DIFFERS from'} "
    f"canonical V0 within 1e-6.",
]

result = {
    "agent_id": "angleD-m4-agent-05",
    "status": "ok",
    "reason": None,
    "reconstruction_method": "imported-function",
    "reconstruction_summary": (
        "V2 — linear single-track yaw-rate with platform-canonical Cα "
        "(via agent's PARAM_BY_PLATFORM) plus per-segment straight-line DC "
        "bias; re-implemented from triage.linear_st_yaw_rate + "
        "run_ladder.per_segment_bias, no fitted-coefficient files needed."
    ),
    "n_segments": n_segs_total,
    "n_samples_after_filter": n_total,
    "baseline_rmse": BASELINE_CANONICAL,
    "baseline_rmse_recomputed": baseline_rmse_recomputed,
    "agent_rmse": agent_rmse,
    "improvement_pct": improvement_pct,
    "notes": "".join(notes_parts),
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, indent=2))
print(f"wrote {OUT}")
