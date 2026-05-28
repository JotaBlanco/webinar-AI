"""Canonical eval for raw-agent-02 — reconstruct B3 (per-platform tuned ladder)
from out/results.json coefficients, run across ALL canonical Ford segments,
compute pooled RMSE, write strict JSON.
"""
from __future__ import annotations

import json
from glob import glob
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI")
AGENT_DIR = REPO_ROOT / "raw-model/idea-01/agent-02"
OUT_JSON = REPO_ROOT / "raw-model/idea-01/_grade/20260527-164838/canonical/raw-agent-02.json"

SEGMENT_GLOBS = [
    "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
]

L_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}

CANONICAL_BASELINE_RMSE = 0.014740020892723483


def load_params():
    with open(AGENT_DIR / "out/results.json") as f:
        r = json.load(f)
    return {
        plat: {
            "L": L_BY_PLATFORM[plat],
            "delta_off": r["per_platform"][plat]["params"]["delta_offset_rad"],
            "K": r["per_platform"][plat]["params"]["K"],
            "lag_samples": r["per_platform"][plat]["params"]["lag_samples"],
        }
        for plat in L_BY_PLATFORM
    }


def predict_segment(df: pd.DataFrame, p: dict) -> np.ndarray:
    """Reconstruct B3: yr = (v/L)*tan(delta - delta_off) / (1 + K*v^2), then
    shift by lag_samples within the segment (negative = move prediction LATER
    in time / earlier index)."""
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy() - p["delta_off"]
    yr = (v / p["L"]) * np.tan(delta) / (1.0 + p["K"] * v * v)

    lag = p["lag_samples"]
    out = yr.copy()
    n = len(yr)
    if lag == 0 or n == 0:
        return out
    if lag > 0:
        # prediction moved earlier: out[i] = yr[i+lag]
        out[: n - lag] = yr[lag:]
        out[n - lag :] = yr[-1]
    else:
        k = -lag
        # prediction moved later: out[i] = yr[i-k]
        out[k:] = yr[:-k]
        out[:k] = yr[0]
    return out


def main():
    params_by_plat = load_params()

    # Gather segments by platform
    seg_paths: list[tuple[str, Path]] = []
    for g in SEGMENT_GLOBS:
        for s in sorted(glob(str(REPO_ROOT / g), recursive=True)):
            p = Path(s)
            # figure platform: it's the dir name right under data/sim/segments
            parts = p.relative_to(REPO_ROOT / "data/sim/segments").parts
            plat = parts[0]
            seg_paths.append((plat, p))

    n_segments = len(seg_paths)

    # Streaming accumulators
    sse_agent = 0.0
    sse_baseline = 0.0
    n_total = 0
    failed_segs = 0

    for plat, path in seg_paths:
        try:
            df = pd.read_csv(path)
        except Exception:
            failed_segs += 1
            continue
        cols_required = ["v_mps", "delta_road_rad", "yaw_rate_meas_rads", "yaw_rate_pred_rads"]
        if not all(c in df.columns for c in cols_required):
            failed_segs += 1
            continue

        # Predict on FULL segment first (so lag-shift is over original time series)
        # Need to handle NaNs in inputs to predict by treating them as zero contribution?
        # Safer: compute predictions then mask filter.
        # Replace NaNs in v/delta with last-valid (forward fill) for prediction continuity,
        # but final RMSE is restricted to filter v>2.0 anyway, which excludes NaN-v rows.
        pred = predict_segment(df, params_by_plat[plat])

        truth = df["yaw_rate_meas_rads"].to_numpy()
        baseline = df["yaw_rate_pred_rads"].to_numpy()
        v = df["v_mps"].to_numpy()

        mask = (v > 2.0) & np.isfinite(truth) & np.isfinite(baseline) & np.isfinite(pred)
        if not mask.any():
            continue

        d_a = pred[mask] - truth[mask]
        d_b = baseline[mask] - truth[mask]
        sse_agent += float(np.sum(d_a * d_a))
        sse_baseline += float(np.sum(d_b * d_b))
        n_total += int(mask.sum())

    agent_rmse = float(np.sqrt(sse_agent / n_total)) if n_total else None
    baseline_rmse_recomputed = float(np.sqrt(sse_baseline / n_total)) if n_total else None
    improvement_pct = (
        (CANONICAL_BASELINE_RMSE - agent_rmse) / CANONICAL_BASELINE_RMSE * 100.0
        if agent_rmse is not None
        else None
    )

    notes_bits = [
        "Reconstructed B3 (per-platform tuned ladder) from out/results.json: "
        "yr = (v/L)*tan(delta - delta0) / (1 + K*v^2), then per-segment integer "
        f"sample shift of lag_samples=-3 (60 ms lead). Pooled over {n_segments} canonical Ford segments under v_mps>2.0."
    ]
    if abs(baseline_rmse_recomputed - CANONICAL_BASELINE_RMSE) > 1e-6:
        notes_bits.append(
            f"baseline_rmse_recomputed ({baseline_rmse_recomputed:.12f}) "
            f"differs from canonical V0 ({CANONICAL_BASELINE_RMSE:.12f}) by "
            f"{baseline_rmse_recomputed - CANONICAL_BASELINE_RMSE:+.2e}."
        )
    if failed_segs:
        notes_bits.append(f"{failed_segs} segments skipped (missing columns / read error).")

    payload = {
        "agent_id": "raw-agent-02",
        "status": "ok",
        "reason": None,
        "reconstruction_method": "json-coeffs",
        "reconstruction_summary": (
            "Re-ran agent's B3 (per-platform tuned ladder) using delta_offset, K, "
            "and lag_samples coefficients lifted from out/results.json; applied per-segment "
            "with per-platform wheelbase L."
        ),
        "n_segments": n_segments,
        "n_samples_after_filter": n_total,
        "baseline_rmse": CANONICAL_BASELINE_RMSE,
        "baseline_rmse_recomputed": baseline_rmse_recomputed,
        "agent_rmse": agent_rmse,
        "improvement_pct": improvement_pct,
        "notes": " ".join(notes_bits),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
