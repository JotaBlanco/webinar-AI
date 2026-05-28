"""segment.py — helper module for the regime-segmentation skill.

Composes with the lateral-fidelity-triage skill: pass DataFrames between them.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

REGIME_DELTA_THR = 0.01    # rad
REGIME_DDELTA_THR = 0.05   # rad/s
DEFAULT_DT = 0.02          # s (50 Hz CSV grid)


def load_and_validate(csv_paths: Iterable[str | Path]) -> pd.DataFrame:
    """Load one or more Ford sim.csv files; tag with __source__; basic sanity checks."""
    frames = []
    for p in csv_paths:
        df = pd.read_csv(p)
        for col in ("t_s", "delta_road_rad"):
            if col not in df.columns:
                raise ValueError(f"{p}: missing column {col!r}")
        t = df["t_s"].to_numpy()
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            raise ValueError(f"{p}: t_s not strictly monotone")
        if np.max(np.diff(t)) > 0.5:
            raise ValueError(f"{p}: gap > 0.5 s in t_s — recheck the source")
        df["__source__"] = str(p)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def tag(df: pd.DataFrame) -> pd.DataFrame:
    """Add a `regime` column. Returns a copy, doesn't mutate."""
    out = df.copy()
    t = out["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt > 0, dt, DEFAULT_DT)
    delta = out["delta_road_rad"].to_numpy()
    ddelta = np.gradient(delta) / dt

    reg = np.full(len(out), "transient", dtype=object)
    reg[np.abs(delta) < REGIME_DELTA_THR] = "straight"
    steady = (np.abs(delta) >= REGIME_DELTA_THR) & (np.abs(ddelta) < REGIME_DDELTA_THR)
    reg[steady] = "steady"
    out["regime"] = reg
    return out


def per_regime_rmse(df: pd.DataFrame, resid_col: str) -> dict[str, float]:
    if "regime" not in df.columns:
        df = tag(df)
    s = df[resid_col].to_numpy()
    overall_mask = np.isfinite(s)
    out = {"overall": float(np.sqrt(np.mean(s[overall_mask] ** 2))) if overall_mask.any() else float("nan")}
    for r in ("straight", "steady", "transient"):
        m = (df["regime"] == r) & overall_mask
        out[r] = float(np.sqrt(np.mean(s[m] ** 2))) if m.any() else float("nan")
    return out
