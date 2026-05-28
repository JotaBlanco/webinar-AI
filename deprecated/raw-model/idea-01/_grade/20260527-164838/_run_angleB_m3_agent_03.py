"""Canonical eval for angleB-m3-agent-03.

Reconstructs the agent's V4 model (their declared favourite):
  V3 = Linear ST with fit C_alpha (scaled) + per-segment yaw-rate bias (on straights)
  V4 = V3 + Ridge residual learner on [v, |a_y_pred|, |delta|, sign(ddelta/dt)] with LOSO

Mach-E physical parameters are used (the agent's model is platform-specific to
Mach-E by construction), but the procedure is rerun on the full canonical
Ford eval set: fit C_alpha scale on cornering rows, fit per-segment bias on
straight rows, then LOSO Ridge over all 545 canonical Ford segments.
"""
from __future__ import annotations
import glob, json, sys, os
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from sklearn.linear_model import Ridge

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI"
OUT = f"{ROOT}/raw-model/idea-01/_grade/20260527-164838/canonical/angleB-m3-agent-03.json"

GLOBS = [
    f"{ROOT}/data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    f"{ROOT}/data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
]

# Mach-E params from agent's tools/lateral_ladder.py
L = 2.984
m = 2336.0
l_f = 1.313
l_r = 1.671
C_af_prior = 286_551.0
C_ar_prior = 355_912.0

V_MIN = 2.0
BASELINE_CANONICAL = 0.014740020892723483


def st_pred(v, d, C_af, C_ar):
    K_us = m * (l_r * C_ar - l_f * C_af) / (L**2 * C_af * C_ar)
    psi_dot = v * d / (L * (1.0 + K_us * v * v))
    mask_low = v < V_MIN
    psi_dot[mask_low] = (v[mask_low] / L) * np.tan(d[mask_low])
    return psi_dot


def rmse(a):
    a = np.asarray(a, dtype=float)
    a = a[np.isfinite(a)]
    return float(np.sqrt(np.mean(a * a))) if len(a) else float("nan")


def main():
    paths = []
    for g in GLOBS:
        paths.extend(sorted(glob.glob(g, recursive=True)))
    print(f"# total segment paths: {len(paths)}", file=sys.stderr)

    segs = []
    needed_cols = ["yaw_rate_meas_rads", "yaw_rate_pred_rads",
                   "delta_road_rad", "v_mps"]
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if not all(c in df.columns for c in needed_cols):
            continue
        df = df.dropna(subset=needed_cols)
        if len(df) < 50:
            continue
        if "a_y_pred_mps2" not in df.columns:
            df["a_y_pred_mps2"] = 0.0
        else:
            df["a_y_pred_mps2"] = df["a_y_pred_mps2"].fillna(0.0)
        sid = "/".join(p.split("/")[-4:-1])
        df = df.copy()
        df["__seg"] = sid
        segs.append(df[needed_cols + ["a_y_pred_mps2", "__seg"]])

    n_segments = len(segs)
    print(f"# loaded {n_segments} segments", file=sys.stderr)
    if not segs:
        raise RuntimeError("no segments loaded")

    all_df = pd.concat(segs, ignore_index=True)
    v = all_df["v_mps"].values.astype(float)
    d = all_df["delta_road_rad"].values.astype(float)
    y_meas = all_df["yaw_rate_meas_rads"].values.astype(float)
    y_v0 = all_df["yaw_rate_pred_rads"].values.astype(float)
    a_y = all_df["a_y_pred_mps2"].values.astype(float)
    segs_arr = all_df["__seg"].values

    # canonical sample filter
    filt = v > V_MIN
    n_samples_after_filter = int(filt.sum())
    print(f"# n_samples_after_filter = {n_samples_after_filter}", file=sys.stderr)

    # --- baseline sanity check
    baseline_rmse_recomputed = rmse(y_v0[filt] - y_meas[filt])
    print(f"# baseline_rmse_recomputed = {baseline_rmse_recomputed}", file=sys.stderr)

    # --- V3: ST with fit C_alpha + per-segment bias
    straight_mask = np.abs(d) < 0.01
    cornering = (np.abs(d) >= 0.01) & (v > V_MIN)

    v_c, d_c, y_c = v[cornering], d[cornering], y_meas[cornering]

    def loss(scale):
        Caf = C_af_prior * scale
        Car = C_ar_prior * scale
        K_us = m * (l_r * Car - l_f * Caf) / (L**2 * Caf * Car)
        pred = v_c * d_c / (L * (1.0 + K_us * v_c * v_c))
        return rmse(pred - y_c)

    res = minimize_scalar(loss, bounds=(0.2, 2.0), method="bounded")
    scale_fit = float(res.x)
    Caf_fit = C_af_prior * scale_fit
    Car_fit = C_ar_prior * scale_fit
    print(f"# scale_fit = {scale_fit}", file=sys.stderr)

    y_v3_raw = st_pred(v, d, Caf_fit, Car_fit)
    r_v3_raw = y_v3_raw - y_meas

    # per-segment bias (on straight rows) — uses pandas indices for speed
    bias3 = {}
    indices = all_df.groupby("__seg").indices
    for sid, idx in indices.items():
        idx = np.asarray(idx)
        st_idx = idx[straight_mask[idx]]
        if len(st_idx) >= 20:
            bias3[sid] = float(np.mean(r_v3_raw[st_idx]))
        else:
            bias3[sid] = 0.0
    bvec3 = all_df["__seg"].map(bias3).values.astype(float)
    y_v3 = y_v3_raw - bvec3
    r_v3 = y_v3 - y_meas

    # --- V4: Ridge residual LOSO on [v, |a_y|, |d|, sign(ddel)]
    # ddelta computed per-segment to avoid spurious gradient across boundaries
    ddel = np.zeros_like(d)
    for sid, idx in indices.items():
        idx = np.asarray(idx)
        # idx returned by groupby.indices is not guaranteed sorted; sort it
        idx_sorted = np.sort(idx)
        ddel[idx_sorted] = np.gradient(d[idx_sorted], 0.02)

    X = np.column_stack([v, np.abs(a_y), np.abs(d), np.sign(ddel)])
    y_resid = r_v3
    unique = np.unique(segs_arr)
    correction = np.zeros_like(y_resid)

    # build seg -> index array (sorted)
    seg_to_idx = {sid: np.sort(np.asarray(idx)) for sid, idx in indices.items()}

    for i, held in enumerate(unique):
        held_idx = seg_to_idx[held]
        train_mask = np.ones(len(segs_arr), dtype=bool)
        train_mask[held_idx] = False
        if train_mask.sum() < 50 or len(held_idx) < 1:
            continue
        mdl = Ridge(alpha=1.0)
        mdl.fit(X[train_mask], y_resid[train_mask])
        correction[held_idx] = mdl.predict(X[held_idx])
        if (i + 1) % 50 == 0:
            print(f"# LOSO {i+1}/{len(unique)}", file=sys.stderr)

    y_v4 = y_v3 - correction

    agent_rmse = rmse((y_v4 - y_meas)[filt])
    improvement_pct = (BASELINE_CANONICAL - agent_rmse) / BASELINE_CANONICAL * 100.0

    result = {
        "agent_id": "angleB-m3-agent-03",
        "status": "ok",
        "reason": None,
        "reconstruction_method": "re-ran-script",
        "reconstruction_summary": (
            "Re-ran agent's V4 (their declared favourite): Linear-ST with fit "
            f"C_alpha (scale={scale_fit:.3f} on cornering rows) + per-segment "
            "yaw-rate bias from straights + Ridge(alpha=1.0) residual learner on "
            "[v, |a_y_pred|, |delta|, sign(ddelta/dt)] with LOSO across all 545 "
            "canonical Ford segments. Agent saved no coefficients to out/, so the "
            "training procedure from tools/lateral_ladder.py was re-executed on the "
            "canonical eval set."
        ),
        "n_segments": n_segments,
        "n_samples_after_filter": n_samples_after_filter,
        "baseline_rmse": BASELINE_CANONICAL,
        "baseline_rmse_recomputed": baseline_rmse_recomputed,
        "agent_rmse": agent_rmse,
        "improvement_pct": improvement_pct,
        "notes": (
            "Agent's V4 uses Mach-E physical parameters (L=2.984, m=2336, l_f=1.313, "
            "l_r=1.671, prior C_alpha 286.6/355.9 kN/rad); these were applied "
            "unchanged to F-150 Lightning segments because the agent shipped only "
            "the Mach-E procedure. C_alpha scale, per-segment bias, and Ridge "
            "residual weights are re-fit on the canonical eval set per the recipe "
            "(no coefficients were persisted in agent's out/). Per-segment delta "
            "gradient computed per-segment to avoid cross-segment artefacts."
        ),
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
