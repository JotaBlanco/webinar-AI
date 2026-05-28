"""Canonical eval for angleD-m2-agent-05.

Favourite model: V4 = V3 (linear-ST with fit C_alpha, per-segment straight-line
bias subtraction) + Ridge residual learner trained leave-one-segment-out over
[v, |a_y|, |delta|, sign(dot(delta))].

The agent did NOT persist C_alpha fit nor Ridge coefficients to disk, and only
ran on 20 Mach-E segments. To reconstruct over the canonical 545 Ford segments,
we replay the agent's exact pipeline (per-platform parameters, multi-start fit
for C_alpha, per-segment straight-line bias subtraction, LOO Ridge over the
canonical segments).
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AGENT_ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-2/agent-05")
sys.path.insert(0, str(AGENT_ROOT / "code"))
sys.path.insert(0, str(AGENT_ROOT / "skills" / "lateral-fidelity-triage"))

import triage  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402

DATA_ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/data")
GLOBS = [
    "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
]
SAMPLE_FILTER_V_MIN = 2.0
TRUTH_COL = "yaw_rate_meas_rads"
OUT_JSON = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/_grade/20260527-164838/canonical/angleD-m2-agent-05.json")
CANONICAL_BASELINE = 0.014740020892723483


def find_segments() -> dict[str, list[Path]]:
    by_plat: dict[str, list[Path]] = {}
    for g in GLOBS:
        plat = g.split("/")[3]
        paths = sorted(Path("/Users/javiquix/Desktop/quixdev/webinar-AI").glob(g))
        by_plat[plat] = paths
    return by_plat


def load_all(by_plat: dict[str, list[Path]]) -> pd.DataFrame:
    frames = []
    for plat, paths in by_plat.items():
        for p in paths:
            df = pd.read_csv(p)
            df["__source__"] = str(p)
            df["__platform__"] = plat
            frames.append(df)
    return pd.concat(frames, ignore_index=True)


def multi_start_fit_c_alpha(v, delta, meas, params) -> tuple[float, float]:
    from scipy.optimize import minimize
    def loss(x):
        cf, cr = x
        pred = triage.linear_st_yaw_rate(
            v, delta,
            L=params.L, l_f=params.l_f, l_r=params.l_r,
            m=params.m, I_z=params.I_z,
            C_alpha_f=cf, C_alpha_r=cr,
        )
        e = pred - meas
        e = e[np.isfinite(e)]
        return float(np.sqrt(np.mean(e**2))) if e.size else float("inf")
    best = (None, float("inf"))
    for cf0 in (8e4, 1.5e5, 2e5, 3e5, 4e5):
        for cr0 in (8e4, 1.5e5, 2e5, 3e5, 4e5):
            r = minimize(loss, [cf0, cr0], method="L-BFGS-B",
                         bounds=[triage.C_ALPHA_BOUNDS, triage.C_ALPHA_BOUNDS])
            if r.fun < best[1]:
                best = ((float(r.x[0]), float(r.x[1])), float(r.fun))
    return best[0]


def main():
    by_plat = find_segments()
    n_seg_total = sum(len(v) for v in by_plat.values())
    print(f"# canonical segments: {n_seg_total} ({ {k: len(v) for k,v in by_plat.items()} })", file=sys.stderr)

    df = load_all(by_plat)
    print(f"# loaded rows: {len(df)}", file=sys.stderr)

    # Sample filter
    keep = df["v_mps"] > SAMPLE_FILTER_V_MIN
    df = df.loc[keep].reset_index(drop=True)
    print(f"# rows after v>{SAMPLE_FILTER_V_MIN}: {len(df)}", file=sys.stderr)

    meas = df[TRUTH_COL].to_numpy()

    # ----- Baseline recomputed: sim.csv's yaw_rate_pred_rads vs truth -----
    baseline_pred = df["yaw_rate_pred_rads"].to_numpy()
    base_resid = baseline_pred - meas
    base_resid_f = base_resid[np.isfinite(base_resid)]
    baseline_rmse_recomputed = float(np.sqrt(np.mean(base_resid_f**2)))
    print(f"# baseline RMSE recomputed: {baseline_rmse_recomputed:.10f}", file=sys.stderr)

    # ----- Build V3 prediction (per-platform fit C_alpha, per-segment straight bias) -----
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    st_pred = np.full(len(df), np.nan)
    fits = {}
    for plat, sub in df.groupby("__platform__"):
        params = PARAM_BY_PLATFORM[plat]
        idx = sub.index.to_numpy()
        cf, cr = multi_start_fit_c_alpha(v[idx], delta[idx], meas[idx], params)
        fits[plat] = {"C_alpha_f": cf, "C_alpha_r": cr}
        print(f"# {plat} fit C_alpha_f={cf:.1f} C_alpha_r={cr:.1f}", file=sys.stderr)
        st_pred[idx] = triage.linear_st_yaw_rate(
            v[idx], delta[idx],
            L=params.L, l_f=params.l_f, l_r=params.l_r,
            m=params.m, I_z=params.I_z,
            C_alpha_f=cf, C_alpha_r=cr,
        )

    resid_v3_raw = st_pred - meas  # pred - meas (agent convention)
    straight = np.abs(delta) < 0.01
    resid_v3 = resid_v3_raw.copy()
    # per-segment straight-line bias subtraction (same as agent)
    seg_groups = df.groupby("__source__").indices
    for src, idx in seg_groups.items():
        idx = np.asarray(idx)
        s_idx = idx[straight[idx]]
        if len(s_idx) > 5:
            bias = float(np.nanmean(resid_v3_raw[s_idx]))
        else:
            bias = 0.0
        resid_v3[idx] = resid_v3_raw[idx] - bias

    v3_rmse = float(np.sqrt(np.nanmean(resid_v3[np.isfinite(resid_v3)]**2)))
    print(f"# V3 pooled RMSE: {v3_rmse:.10f}", file=sys.stderr)

    # ----- V4: Ridge residual learner, LOO over canonical segments -----
    # Features: [v, |a_y|, |delta|, sign(ddelta))]
    from sklearn.linear_model import Ridge

    # ddelta computed per-segment (to match agent's intent — np.gradient over
    # a contiguous segment, not across segment boundaries).
    t = df["t_s"].to_numpy()
    ddelta = np.zeros(len(df))
    for src, idx in seg_groups.items():
        idx = np.asarray(idx)
        ts = t[idx]
        ds = delta[idx]
        dt = np.diff(ts, prepend=ts[0])
        dt = np.where(dt > 0, dt, 0.02)
        ddelta[idx] = np.gradient(ds) / dt

    a_y = df["a_y_pred_mps2"].to_numpy() if "a_y_pred_mps2" in df.columns else np.zeros(len(df))

    X = np.column_stack([
        v,
        np.abs(a_y),
        np.abs(delta),
        np.sign(ddelta),
    ])
    y = resid_v3.copy()

    # NaN/inf guard
    valid = np.isfinite(X).all(axis=1) & np.isfinite(y)
    X_v = X[valid]
    y_v = y[valid]
    src_v = df["__source__"].to_numpy()[valid]

    # LOO over segments — Ridge has closed form, fast.
    segs = np.unique(src_v)
    oof = np.full(len(y_v), np.nan)
    # Precompute mapping
    seg_to_mask = {s: (src_v == s) for s in segs}
    for i, seg in enumerate(segs):
        test_mask = seg_to_mask[seg]
        train_mask = ~test_mask
        model = Ridge(alpha=1.0).fit(X_v[train_mask], y_v[train_mask])
        oof[test_mask] = model.predict(X_v[test_mask])
        if (i+1) % 50 == 0:
            print(f"#   LOO {i+1}/{len(segs)}", file=sys.stderr)

    resid_v4 = y_v - oof
    agent_rmse = float(np.sqrt(np.mean(resid_v4**2)))
    n_samples_used = int(valid.sum())
    print(f"# V4 (agent) RMSE: {agent_rmse:.10f}  (n_samples={n_samples_used})", file=sys.stderr)

    improvement_pct = (CANONICAL_BASELINE - agent_rmse) / CANONICAL_BASELINE * 100.0

    notes = (
        "Reconstructed V4 = V3 (linear-ST with multi-start fit C_alpha per platform, "
        "per-segment straight-line bias subtraction) + Ridge(alpha=1.0) residual "
        "learner over [v, |a_y|, |delta|, sign(ddot delta)] with leave-one-segment-out "
        "across all 545 canonical Ford segments. Agent persisted no coefficients, so "
        "C_alpha and Ridge were refit on the canonical set following the agent's "
        f"exact pipeline. Per-platform fits: {fits}. "
        "Agent's reported numbers were on 20 Mach-E segments only (Mach-E V4 RMSE "
        "0.01499); canonical pooling across both Ford platforms (Mach-E + Lightning) "
        "and per-platform Cα refitting move the headline. "
        "Baseline_rmse_recomputed matches canonical to within "
        f"{abs(baseline_rmse_recomputed - CANONICAL_BASELINE):.2e}."
    )

    n_samples_after_filter = int(len(df))  # rows used in metric pool

    out = {
        "agent_id": "angleD-m2-agent-05",
        "status": "ok",
        "reason": None,
        "reconstruction_method": "imported-function",
        "reconstruction_summary": (
            "Re-ran the agent's V4 pipeline (linear-ST with per-platform multi-start "
            "C_alpha fit + per-segment straight-line bias + Ridge residual learner "
            "LOO over segments) using triage.linear_st_yaw_rate and a Ridge model "
            "matching the agent's residual_learner_loo implementation."
        ),
        "n_segments": n_seg_total,
        "n_samples_after_filter": n_samples_after_filter,
        "baseline_rmse": CANONICAL_BASELINE,
        "baseline_rmse_recomputed": baseline_rmse_recomputed,
        "agent_rmse": agent_rmse,
        "improvement_pct": improvement_pct,
        "notes": notes,
    }

    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"# wrote {OUT_JSON}", file=sys.stderr)


if __name__ == "__main__":
    main()
