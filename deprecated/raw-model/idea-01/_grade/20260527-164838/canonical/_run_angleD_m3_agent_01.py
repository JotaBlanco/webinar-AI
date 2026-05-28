#!/usr/bin/env python3
"""Canonical eval for angleD-m3-agent-01.

Reconstructs the agent's "best" V1 model:
  v1_pred = (v/L) * tan(delta)  -  per_segment_bias
  per_segment_bias = mean( (v/L)*tan(delta) - meas )  over rows where |delta| < 0.01

Platform-specific L is used (Mach-E L=2.984, F-150 Lightning L=3.70).
Per-segment bias is computed per sim.csv segment from straight-line samples in that
segment (no filter on v for bias estimation, matching agent code).

RMSE is then pooled over all rows where v_mps > 2.0 across all 545 Ford segments.
"""
from __future__ import annotations
import glob
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path("/Users/javiquix/Desktop/quixdev/webinar-AI")
OUT_JSON = REPO / "raw-model/idea-01/_grade/20260527-164838/canonical/angleD-m3-agent-01.json"

L_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}

CANON_BASELINE = 0.014740020892723483

SEGMENT_GLOBS = [
    "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
]


def platform_for(csv_path: str) -> str:
    for plat in L_BY_PLATFORM:
        if f"/segments/{plat}/" in csv_path:
            return plat
    raise ValueError(f"unknown platform in path: {csv_path}")


def main() -> int:
    csvs: list[str] = []
    for g in SEGMENT_GLOBS:
        csvs.extend(sorted(glob.glob(str(REPO / g), recursive=True)))
    n_segments = len(csvs)
    print(f"Found {n_segments} canonical segments")

    # accumulators for pooled RMSE
    agent_sse = 0.0   # sum of squared errors  (pred - truth)^2 over filtered samples
    base_sse = 0.0
    n_after = 0

    required = {"v_mps", "delta_road_rad", "yaw_rate_meas_rads", "yaw_rate_pred_rads"}

    for i, p in enumerate(csvs):
        df = pd.read_csv(p)
        miss = required - set(df.columns)
        if miss:
            raise ValueError(f"missing cols in {p}: {miss}")

        plat = platform_for(p)
        L = L_BY_PLATFORM[plat]

        v = df["v_mps"].to_numpy(dtype=float)
        delta = df["delta_road_rad"].to_numpy(dtype=float)
        meas = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
        base_pred = df["yaw_rate_pred_rads"].to_numpy(dtype=float)

        # KS prediction with platform L
        ks_pred = (v / L) * np.tan(delta)

        # per-segment yaw-gyro bias from straight-line samples (|delta| < 0.01)
        straight_mask = np.abs(delta) < 0.01
        if straight_mask.any():
            bias = float(np.mean(ks_pred[straight_mask] - meas[straight_mask]))
        else:
            bias = 0.0
        agent_pred = ks_pred - bias

        # canonical sample filter
        keep = v > 2.0
        # also drop non-finite (defensive)
        finite = np.isfinite(meas) & np.isfinite(agent_pred) & np.isfinite(base_pred)
        keep = keep & finite

        ne = (agent_pred[keep] - meas[keep]) ** 2
        be = (base_pred[keep] - meas[keep]) ** 2
        agent_sse += float(ne.sum())
        base_sse += float(be.sum())
        n_after += int(keep.sum())

        if (i + 1) % 50 == 0:
            print(f"  processed {i+1}/{n_segments} segments, n_after={n_after}")

    agent_rmse = float(np.sqrt(agent_sse / n_after))
    base_rmse_recomp = float(np.sqrt(base_sse / n_after))
    improvement_pct = (CANON_BASELINE - agent_rmse) / CANON_BASELINE * 100.0

    print(f"n_segments={n_segments}  n_samples_after_filter={n_after}")
    print(f"baseline (canonical): {CANON_BASELINE:.10f}")
    print(f"baseline (recomputed): {base_rmse_recomp:.10f}")
    print(f"agent V1 RMSE:        {agent_rmse:.10f}")
    print(f"improvement: {improvement_pct:.4f}%")

    base_match = abs(base_rmse_recomp - CANON_BASELINE) < 1e-6
    notes_parts = []
    notes_parts.append(
        "Reconstructed V1 = (v/L)*tan(delta) - per_segment_bias, with bias = mean of "
        "(ks_pred - meas) over rows with |delta|<0.01 in each segment; "
        "L=2.984 for Mach-E, L=3.70 for F-150 Lightning (from agent's parameters.py)."
    )
    if not base_match:
        notes_parts.append(
            f"baseline recomputation {base_rmse_recomp:.10f} differs from canonical "
            f"{CANON_BASELINE:.10f} by {abs(base_rmse_recomp-CANON_BASELINE):.2e}."
        )
    notes_parts.append(
        "Agent originally validated V1 only on 30 Mach-E segments; canonical run "
        "extends per-segment-bias logic identically to all 545 Ford segments."
    )
    result = {
        "agent_id": "angleD-m3-agent-01",
        "status": "ok",
        "reason": None,
        "reconstruction_method": "json-coeffs",  # parameters from agent's parameters.py + bias computed per-segment per REPORT
        "reconstruction_summary": (
            "V1 = KS yaw-rate with platform wheelbase L (Mach-E 2.984, F-150 Lightning 3.70) "
            "minus a per-segment yaw-gyro bias estimated from straight-line samples "
            "(|delta|<0.01) in that segment, exactly as in the agent's run_ladder.py."
        ),
        "n_segments": n_segments,
        "n_samples_after_filter": n_after,
        "baseline_rmse": CANON_BASELINE,
        "baseline_rmse_recomputed": base_rmse_recomp,
        "agent_rmse": agent_rmse,
        "improvement_pct": improvement_pct,
        "notes": " ".join(notes_parts),
    }
    OUT_JSON.write_text(json.dumps(result, indent=2))
    print(f"wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
