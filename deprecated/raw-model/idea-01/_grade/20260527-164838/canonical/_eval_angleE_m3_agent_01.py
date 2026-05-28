"""Canonical eval for angleE-m3-agent-01 (V1 KS-recalibrated with per-segment gyro-bias).

Per the agent's REPORT (webinar-angle-E/module-3/agent-01/REPORT.md):
  - Variant ladder V0..V3 evaluated; only V1 improves over V0.
  - "V1 owns the entire net improvement." (REPORT § Attribution)
  - V2 and V3 are regressions; V3 optimizer made zero progress and equals the prior.
  - Net improvement = V1's per-segment yaw-gyro bias correction on straights.
  => Favourite/best variant = V1.

V1 model (skills/yaw-divergence-triage/triage.py: v1_ks_recalibrated):
  pred_ks  = (v_mps / L) * tan(delta_road_rad)                      # KS yaw rate, L from platform
  bias     = mean(pred_ks - yaw_rate_meas_rads) over STRAIGHT rows  # per-segment
              where straight = |delta_road_rad| < 0.01 rad
  pred_v1  = pred_ks - bias                                          # final per-sample prediction

L (wheelbase) is platform-dependent (code/parameters.py):
  FORD_MUSTANG_MACH_E_MK1 : L = 2.984 m
  FORD_F_150_LIGHTNING_MK1: L = 3.70  m

Canonical eval pools BOTH Ford platforms (545 segments). The agent fit V1 only
on Mach-E, but V1's only "parameter" per segment is the bias, computed within
that segment from its own straight rows. So applying V1 to F-150 segments uses
the F-150 wheelbase and that segment's own bias — a faithful application of
the agent's shipped model to each canonical segment.

Filter: v_mps > 2.0 (applied at RMSE-pooling time, not at bias-computation time —
matches the agent's _run.py which computes bias over all straight rows).
"""
import glob, json, os
from datetime import datetime
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI"
GLOBS = {
    "FORD_MUSTANG_MACH_E_MK1": f"{ROOT}/data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "FORD_F_150_LIGHTNING_MK1": f"{ROOT}/data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
}
L_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}
DELTA_THR = 0.01  # straight regime threshold from triage.DELTA_THR

TRUTH = "yaw_rate_meas_rads"
PRED0 = "yaw_rate_pred_rads"
VCOL = "v_mps"
DCOL = "delta_road_rad"

CANON_BASELINE_RMSE = 0.014740020892723483

OUT_JSON = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/_grade/20260527-164838/canonical/angleE-m3-agent-01.json"


def main():
    sse_base = 0.0
    sse_agent = 0.0
    n_total = 0
    n_segments = 0

    for platform, pattern in GLOBS.items():
        L = L_BY_PLATFORM[platform]
        paths = sorted(glob.glob(pattern, recursive=True))
        for p in paths:
            df = pd.read_csv(p)
            if not {TRUTH, PRED0, VCOL, DCOL}.issubset(df.columns):
                # skip malformed (shouldn't happen)
                continue
            v = df[VCOL].to_numpy(dtype=float)
            delta = df[DCOL].to_numpy(dtype=float)
            meas = df[TRUTH].to_numpy(dtype=float)
            pred0 = df[PRED0].to_numpy(dtype=float)

            # KS prediction with platform L
            pred_ks = (v / L) * np.tan(delta)

            # Per-segment bias from straight rows (|delta| < 0.01)
            straight = np.abs(delta) < DELTA_THR
            if straight.any():
                diff = pred_ks[straight] - meas[straight]
                diff = diff[np.isfinite(diff)]
                bias = float(np.mean(diff)) if diff.size else 0.0
            else:
                bias = 0.0

            pred_v1 = pred_ks - bias

            # Apply v_mps > 2.0 filter at pooling time
            mask = (v > 2.0) & np.isfinite(meas) & np.isfinite(pred0) & np.isfinite(pred_v1)
            if not mask.any():
                n_segments += 1
                continue

            e_base = pred0[mask] - meas[mask]
            e_agent = pred_v1[mask] - meas[mask]

            sse_base += float(np.sum(e_base ** 2))
            sse_agent += float(np.sum(e_agent ** 2))
            n_total += int(mask.sum())
            n_segments += 1

    baseline_rmse_recomputed = float(np.sqrt(sse_base / n_total))
    agent_rmse = float(np.sqrt(sse_agent / n_total))
    improvement_pct = (CANON_BASELINE_RMSE - agent_rmse) / CANON_BASELINE_RMSE * 100.0

    notes_parts = []
    if abs(baseline_rmse_recomputed - CANON_BASELINE_RMSE) > 1e-6:
        notes_parts.append(
            f"baseline recomputation drift: {baseline_rmse_recomputed - CANON_BASELINE_RMSE:+.3e}"
        )
    notes_parts.append(
        "V1 = platform-L KS yaw rate minus per-segment straight-regime bias "
        "(|delta|<0.01 rad); applied to both Ford platforms with each platform's own L."
    )

    out = {
        "agent_id": "angleE-m3-agent-01",
        "status": "ok",
        "reason": None,
        "reconstruction_method": "imported-function",
        "reconstruction_summary": (
            "Re-implemented V1 (KS recalibrated + per-segment straight-regime gyro-bias) "
            "exactly as in skills/yaw-divergence-triage/triage.py::v1_ks_recalibrated, "
            "using platform wheelbase L from code/parameters.py."
        ),
        "n_segments": n_segments,
        "n_samples_after_filter": n_total,
        "baseline_rmse": CANON_BASELINE_RMSE,
        "baseline_rmse_recomputed": baseline_rmse_recomputed,
        "agent_rmse": agent_rmse,
        "improvement_pct": improvement_pct,
        "notes": " | ".join(notes_parts),
    }
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=2)
    print(f"wrote {OUT_JSON}")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
