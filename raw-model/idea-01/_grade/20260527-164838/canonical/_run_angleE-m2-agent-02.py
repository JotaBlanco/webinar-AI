#!/usr/bin/env python3
"""Canonical re-eval for angleE-m2-agent-02.

Reconstructs the agent's V1 model (their declared best) from REPORT + tools/step4:
    ks_pred = (v / L) * tan(delta_road_rad)            # L = canonical wheelbase per platform
    bias    = mean(ks_pred - meas)  over straight rows within each segment
    v1_pred = ks_pred - bias

Regime ("straight"): |delta_road_rad| < 0.01 rad   (per tools/step2_segment_by_regime.py)

Pooled RMSE is taken over all qualifying samples (v_mps > 2.0), across ALL 545
canonical Ford segments.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path("/Users/javiquix/Desktop/quixdev/webinar-AI")
DATA_ROOT = REPO / "data" / "sim" / "segments"
OUT_PATH = REPO / "raw-model/idea-01/_grade/20260527-164838/canonical/angleE-m2-agent-02.json"

# Canonical V0 baseline reported in prompt:
CANONICAL_BASELINE_RMSE = 0.014740020892723483

# Platform wheelbases from code/parameters.py (canonical openpilot carParams values).
L_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}

DELTA_THR = 0.01  # rad — "straight" regime threshold (step2)
V_FILTER = 2.0    # canonical sample_filter v_mps > 2.0


def main() -> int:
    sq_err_base = 0.0
    sq_err_agent = 0.0
    n_samples_filter = 0
    n_segments = 0

    for platform, L in L_BY_PLATFORM.items():
        seg_files = sorted((DATA_ROOT / platform).rglob("sim.csv"))
        for p in seg_files:
            df = pd.read_csv(p)
            n_segments += 1

            v = df["v_mps"].to_numpy(dtype=float)
            delta = df["delta_road_rad"].to_numpy(dtype=float)
            meas = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
            v0_pred = df["yaw_rate_pred_rads"].to_numpy(dtype=float)

            # Reconstruct V1 for this segment.
            ks_pred = (v / L) * np.tan(delta)

            # Per-segment straight-regime bias (computed on ALL rows of the segment,
            # matching the agent's training behaviour — they did not apply v>2 when
            # computing bias).
            straight_mask = np.abs(delta) < DELTA_THR
            if straight_mask.any():
                bias = float(np.mean(ks_pred[straight_mask] - meas[straight_mask]))
            else:
                bias = 0.0
            v1_pred = ks_pred - bias

            # Apply canonical sample filter for the RMSE accumulator.
            qual = (v > V_FILTER) & np.isfinite(v1_pred) & np.isfinite(meas) & np.isfinite(v0_pred)
            if not qual.any():
                continue

            e_agent = v1_pred[qual] - meas[qual]
            e_base = v0_pred[qual] - meas[qual]

            sq_err_agent += float(np.sum(e_agent ** 2))
            sq_err_base += float(np.sum(e_base ** 2))
            n_samples_filter += int(qual.sum())

    agent_rmse = math.sqrt(sq_err_agent / n_samples_filter)
    baseline_rmse_recomputed = math.sqrt(sq_err_base / n_samples_filter)
    improvement_pct = (CANONICAL_BASELINE_RMSE - agent_rmse) / CANONICAL_BASELINE_RMSE * 100.0

    notes_bits = []
    if abs(baseline_rmse_recomputed - CANONICAL_BASELINE_RMSE) > 1e-6:
        notes_bits.append(
            f"baseline_rmse_recomputed differs from cached canonical by "
            f"{baseline_rmse_recomputed - CANONICAL_BASELINE_RMSE:.3e}"
        )
    notes_bits.append(
        "Reconstructed V1 = KS pred (v/L · tan δ) minus per-segment straight-regime "
        "yaw bias, exactly per tools/step4_run_st_upgrade.py; bias is fitted on all "
        "rows of each segment (no v>2 gate on bias computation) and the canonical "
        "sample_filter (v>2) is applied only when accumulating RMSE."
    )
    notes_bits.append(
        "Agent's own (MachE-only, unfiltered) V1 RMSE was 0.01469; pooling across "
        "both Ford platforms with v>2 filter is the cross-agent canonical number."
    )

    out = {
        "agent_id": "angleE-m2-agent-02",
        "status": "ok",
        "reason": None,
        "reconstruction_method": "json-coeffs",
        "reconstruction_summary": (
            "Re-ran the agent's declared best variant V1 (KS recalib with canonical "
            "L + per-segment straight-regime yaw-gyro bias), reconstructed from the "
            "equation in REPORT.md and the explicit implementation in "
            "tools/step4_run_st_upgrade.py; per-segment bias is derived directly from "
            "each canonical sim.csv (no saved coefficients needed beyond canonical L)."
        ),
        "n_segments": n_segments,
        "n_samples_after_filter": n_samples_filter,
        "baseline_rmse": CANONICAL_BASELINE_RMSE,
        "baseline_rmse_recomputed": baseline_rmse_recomputed,
        "agent_rmse": agent_rmse,
        "improvement_pct": improvement_pct,
        "notes": " ".join(notes_bits),
    }
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"wrote {OUT_PATH}")
    print(json.dumps({k: out[k] for k in ("n_segments", "n_samples_after_filter",
                                          "baseline_rmse_recomputed", "agent_rmse",
                                          "improvement_pct")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
