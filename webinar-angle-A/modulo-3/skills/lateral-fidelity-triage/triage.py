"""Helpers for the lateral-fidelity-triage skill.

Read `SKILL.md` for the procedure. This file is the *plumbing* (segment loading,
regime masking, RMSE/variance bookkeeping) so the agent's variant implementations
(V1 param fit, V2 ST, V3 C_alpha fit, V4 residual ML) can stay short.

No model code lives here on purpose — model variants are written by the agent
in the report, with the structure imported from `code/ks_model.py` and the
parameters from `code/parameters.py`. This file only handles measurement and
attribution.
"""

from __future__ import annotations

import csv
import glob
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


FORD_PLATFORMS = ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1")


@dataclass
class Segment:
    """One Ford sim.csv loaded into numpy."""
    path: str
    platform: str
    t: np.ndarray           # [s]
    delta_road: np.ndarray  # [rad]      KS input (road-wheel)
    v: np.ndarray           # [m/s]      measured speed
    yaw_meas: np.ndarray    # [rad/s]    truth
    yaw_pred_v0: np.ndarray # [rad/s]    KS baseline already in the CSV

    @property
    def dt(self) -> float:
        return float(np.median(np.diff(self.t)))


def discover_ford_segments(data_root: str = "data") -> list[str]:
    paths: list[str] = []
    for plat in FORD_PLATFORMS:
        paths.extend(sorted(glob.glob(f"{data_root}/sim/segments/{plat}/**/sim.csv", recursive=True)))
    return paths


def load_segment(path: str, trim_seconds: float = 1.0) -> Segment:
    """Load one Ford sim.csv into a Segment, trimming `trim_seconds` from each end."""
    cols: dict[str, list[float]] = {}
    with open(path, newline="") as f:
        rd = csv.DictReader(f)
        for row in rd:
            for k, v in row.items():
                cols.setdefault(k, []).append(float(v) if v != "" else float("nan"))
    arr = {k: np.asarray(v, dtype=float) for k, v in cols.items()}

    t = arr["t_s"]
    dt = float(np.median(np.diff(t)))
    n_trim = int(round(trim_seconds / dt))
    sl = slice(n_trim, len(t) - n_trim)

    platform = _platform_from_path(path)
    return Segment(
        path=path,
        platform=platform,
        t=t[sl],
        delta_road=arr["delta_road_rad"][sl],
        v=arr["v_mps"][sl],
        yaw_meas=arr["yaw_rate_meas_rads"][sl],
        yaw_pred_v0=arr["yaw_rate_pred_rads"][sl],
    )


def _platform_from_path(path: str) -> str:
    for plat in FORD_PLATFORMS:
        if plat in path:
            return plat
    raise ValueError(f"Could not infer platform from path: {path}")


# ---------- Regime masking ----------------------------------------------------

@dataclass
class RegimeMasks:
    straight: np.ndarray
    steady: np.ndarray
    transient: np.ndarray


def regime_masks(
    yaw_meas: np.ndarray,
    dt: float,
    straight_thresh: float = 0.05,            # rad/s
    transient_dyaw_thresh: float = 0.3,        # rad/s²
    straight_min_run_s: float = 1.0,
) -> RegimeMasks:
    """Boolean masks for the three regimes described in SKILL.md § "Regime segmentation".

    Mutual exclusivity: transient wins over straight; the rest is steady-state.
    """
    dyaw = np.gradient(yaw_meas, dt)
    transient = np.abs(dyaw) > transient_dyaw_thresh

    raw_straight = np.abs(yaw_meas) < straight_thresh
    # Require a continuous run of `straight_min_run_s` to call it straight.
    min_run = int(round(straight_min_run_s / dt))
    straight = _runs_at_least(raw_straight, min_run)
    straight &= ~transient
    steady = ~straight & ~transient
    return RegimeMasks(straight=straight, steady=steady, transient=transient)


def _runs_at_least(mask: np.ndarray, min_run: int) -> np.ndarray:
    """True where `mask` is part of a continuous True-run of length ≥ min_run."""
    out = np.zeros_like(mask, dtype=bool)
    n = len(mask)
    i = 0
    while i < n:
        if not mask[i]:
            i += 1
            continue
        j = i
        while j < n and mask[j]:
            j += 1
        if j - i >= min_run:
            out[i:j] = True
        i = j
    return out


# ---------- Metric bookkeeping ------------------------------------------------

def rmse(resid: np.ndarray) -> float:
    return float(np.sqrt(np.mean(resid ** 2)))


def variance(resid: np.ndarray) -> float:
    return float(np.var(resid))


@dataclass
class VariantRow:
    variant: str
    rmse_overall: float
    rmse_straight: float
    rmse_steady: float
    rmse_transient: float
    delta_overall_vs_prev: float | None
    pct_variance_closed: float  # vs baseline


def score_variant(
    name: str,
    yaw_pred_concat: np.ndarray,
    yaw_meas_concat: np.ndarray,
    masks_concat: RegimeMasks,
    baseline_resid_var: float,
    prev_rmse_overall: float | None,
) -> VariantRow:
    resid = yaw_pred_concat - yaw_meas_concat
    r_overall = rmse(resid)
    return VariantRow(
        variant=name,
        rmse_overall=r_overall,
        rmse_straight=rmse(resid[masks_concat.straight]),
        rmse_steady=rmse(resid[masks_concat.steady]),
        rmse_transient=rmse(resid[masks_concat.transient]),
        delta_overall_vs_prev=(r_overall - prev_rmse_overall) if prev_rmse_overall is not None else None,
        pct_variance_closed=100.0 * (1.0 - variance(resid) / baseline_resid_var),
    )


def concat(segments: Iterable[Segment], attr: str) -> np.ndarray:
    return np.concatenate([getattr(s, attr) for s in segments])


def concat_masks(segments: list[Segment]) -> RegimeMasks:
    """Compute per-segment masks (each on its own dt) then concatenate."""
    sm: list[RegimeMasks] = [regime_masks(s.yaw_meas, s.dt) for s in segments]
    return RegimeMasks(
        straight=np.concatenate([m.straight for m in sm]),
        steady=np.concatenate([m.steady for m in sm]),
        transient=np.concatenate([m.transient for m in sm]),
    )


# ---------- Reporting helpers -------------------------------------------------

def attribution_markdown_table(rows: list[VariantRow]) -> str:
    head = "| variant | RMSE_overall | RMSE_straight | RMSE_steady | RMSE_transient | Δ_overall_vs_prev | pct_variance_closed |"
    sep =  "|---|---:|---:|---:|---:|---:|---:|"
    body = []
    for r in rows:
        d = "—" if r.delta_overall_vs_prev is None else f"{r.delta_overall_vs_prev:+.4f}"
        body.append(
            f"| {r.variant} | {r.rmse_overall:.4f} | {r.rmse_straight:.4f} | "
            f"{r.rmse_steady:.4f} | {r.rmse_transient:.4f} | {d} | {r.pct_variance_closed:+.1f}% |"
        )
    return "\n".join([head, sep, *body])


if __name__ == "__main__":
    # Smoke test against the four Ford segments and the V0 baseline column.
    seg_paths = discover_ford_segments()
    print(f"Found {len(seg_paths)} Ford segments")
    segs = [load_segment(p) for p in seg_paths]
    masks = concat_masks(segs)
    yaw_meas_c = concat(segs, "yaw_meas")
    yaw_v0_c = concat(segs, "yaw_pred_v0")
    base_var = variance(yaw_v0_c - yaw_meas_c)
    row = score_variant("V0 — KS baseline", yaw_v0_c, yaw_meas_c, masks, base_var, None)
    print(attribution_markdown_table([row]))
    print(f"\nRegime sample counts — straight={masks.straight.sum()}, "
          f"steady={masks.steady.sum()}, transient={masks.transient.sum()}")
