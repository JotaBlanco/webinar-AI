#!/usr/bin/env python3
"""ablation-study/run.py — reference implementation of the disciplined ablation.

This is a *reference*. You can implement the loop yourself in `tools/` if you
prefer — what matters is the discipline in SKILL.md (interleaved split,
additive monotone variants, marginal attribution, attribution-coherence check,
regression flagging, per-segment/per-platform labelling).

Usage:
    python3 run.py <variant-list-script.py>

`<variant-list-script.py>` must expose:
    - VARIANTS: list[tuple[str, callable]]   # (name, function) pairs
    - SEGMENT_GLOB: str                       # glob under data/sim/segments
    - REGIMES: dict[str, callable]            # regime predicates (optional;
                                              # defaults to baseline-residual's)

Each callable in VARIANTS takes a DataFrame and returns a new column for
yaw_rate_pred_rads (the rest of the row stays the same; the runner recomputes
yaw_rate_resid_rads and a_y_pred = v * ψ̇ accordingly).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REGIME_DELTA_THR = 0.01
REGIME_DDELTA_THR = 0.05
COHERENCE_TOL = 0.15


def regime_mask(df: pd.DataFrame) -> pd.Series:
    delta = df["delta_road_rad"].to_numpy()
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt <= 0, 0.02, dt)
    ddelta = np.gradient(delta) / dt
    out = np.full(len(df), "transient", dtype=object)
    out[np.abs(delta) < REGIME_DELTA_THR] = "straight"
    steady = (np.abs(delta) >= REGIME_DELTA_THR) & (np.abs(ddelta) < REGIME_DDELTA_THR)
    out[steady] = "steady"
    return pd.Series(out, index=df.index, name="regime")


def rmse(a) -> float:
    s = np.asarray(a, dtype=float)
    s = s[np.isfinite(s)]
    return float(np.sqrt(np.mean(s ** 2))) if s.size else float("nan")


def per_regime_rmse(df: pd.DataFrame, mask: pd.Series, col: str) -> dict:
    out = {"overall": rmse(df[col])}
    for r in ("straight", "steady", "transient"):
        out[r] = rmse(df.loc[mask == r, col])
    return out


def interleaved_split(n: int, fold_size: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Returns (train_idx, test_idx). Every fold_size-th index → test."""
    idx = np.arange(n)
    test = idx[fold_size - 1::fold_size]
    train = np.setdiff1d(idx, test)
    return train, test


def main():
    if len(sys.argv) != 2:
        print("usage: run.py <variant-list-script.py>", file=sys.stderr)
        sys.exit(2)
    spec_path = Path(sys.argv[1])
    spec = importlib.util.spec_from_file_location("variants", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    csvs = sorted(Path("data/sim/segments").glob(mod.SEGMENT_GLOB))
    frames = [pd.read_csv(p) for p in csvs]
    big = pd.concat(frames, ignore_index=True)
    mask = regime_mask(big)
    n = len(big)
    print(f"Segments: {len(csvs)}  samples: {n}")

    # V0 baseline
    v0 = per_regime_rmse(big, mask, "yaw_rate_resid_rads")
    rows = [("V0", v0, None)]
    print(f"V0 overall RMSE: {v0['overall']:.5f}")

    # Apply each variant in fixed order
    work = big.copy()
    prev = v0["overall"]
    for i, (name, fn) in enumerate(mod.VARIANTS, start=1):
        new_pred = fn(work)
        work = work.copy()
        work["yaw_rate_pred_rads"] = new_pred
        work["yaw_rate_resid_rads"] = work["yaw_rate_pred_rads"] - work["yaw_rate_meas_rads"]
        work["a_y_pred_mps2"] = work["v_mps"] * work["yaw_rate_pred_rads"]
        work["a_y_resid_mps2"] = work["a_y_pred_mps2"] - work["a_lat_meas_mps2"]
        rm = per_regime_rmse(work, mask, "yaw_rate_resid_rads")
        marginal = prev - rm["overall"]
        flag = "regression" if marginal < 0 else ""
        rows.append((f"V{i} {name}", rm, marginal))
        print(f"V{i} {name:<30s} overall {rm['overall']:.5f}  marginal {marginal:+.5f}  {flag}")
        prev = rm["overall"]

    total = v0["overall"] - rows[-1][1]["overall"]
    marg_sum = sum(r[2] for r in rows[1:] if r[2] is not None)
    err = abs(marg_sum - total) / abs(total) if total else float("inf")
    print(f"\nattribution coherence: |Σmarg − total|/|total| = {err:.3f}  (must be < {COHERENCE_TOL})")
    sys.exit(0 if err < COHERENCE_TOL else 1)


if __name__ == "__main__":
    main()
