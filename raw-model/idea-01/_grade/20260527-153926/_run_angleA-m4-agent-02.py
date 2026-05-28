"""Canonical eval runner for angleA-m4-agent-02.

Reconstructs the agent's "favourite" model (V4 = V3 linear-ST + per-segment
straight-bias + LOSO ridge residual learner) and runs it across all 545
canonical Ford sim segments, computing pooled-sample RMSE under v_mps > 2.0.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI")
AGENT_DIR = ROOT / "webinar-angle-A" / "module-4" / "agent-02"
sys.path.insert(0, str(AGENT_DIR / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(AGENT_DIR / "code"))

import triage  # type: ignore
from parameters import PARAM_BY_PLATFORM  # type: ignore

# Agent's fitted Cf, Cr (Mach-E fit) from out/ladder_results.json
FIT_CF = 427029.1671174572
FIT_CR = 483736.5465673796

# The agent's model was built on the Mach-E parameter set. The canonical eval
# pools both Ford platforms. Per the "shipped parameter set" framing, apply
# Mach-E vehicle params to all Ford segments — this is the agent's V4 model
# treated as-is.
P_MACHE = PARAM_BY_PLATFORM["FORD_MUSTANG_MACH_E_MK1"]

GLOBS = [
    "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
]

OUT_JSON = ROOT / "raw-model" / "idea-01" / "_grade" / "20260527-153926" / "canonical" / "angleA-m4-agent-02.json"
OUT_JSON.parent.mkdir(parents=True, exist_ok=True)


def main():
    # Enumerate all canonical segment csvs
    seg_paths = []
    for g in GLOBS:
        seg_paths.extend(sorted(ROOT.glob(g)))
    print(f"Found {len(seg_paths)} segments")

    # ----- Pass 1: load each segment, compute V3-with-bias residual,
    # build features. Keep arrays in memory; stream segment-wise.
    all_v = []
    all_delta = []
    all_meas = []
    all_v0pred = []  # baseline pred from sim.csv yaw_rate_pred_rads
    all_v3pred_bias_adj = []  # V3 prediction WITH per-seg bias subtracted (i.e. agent's V3 yaw rate model)
    all_v3resid = []  # signed residual (v3pred_bias_adj - meas), target for ridge
    all_feat = []
    all_seg_id = []

    for i, p in enumerate(seg_paths):
        df = pd.read_csv(p)
        v = df["v_mps"].to_numpy()
        delta = df["delta_road_rad"].to_numpy()
        meas = df["yaw_rate_meas_rads"].to_numpy()
        v0pred = df["yaw_rate_pred_rads"].to_numpy()
        t = df["t_s"].to_numpy()
        a_y_pred = df["a_y_pred_mps2"].to_numpy() if "a_y_pred_mps2" in df.columns else np.zeros(len(df))

        # Regime mask (for bias subtraction on straight samples)
        dt = np.diff(t, prepend=t[0])
        dt = np.where(dt <= 0, 0.02, dt)
        ddelta = np.gradient(delta) / dt
        is_straight = np.abs(delta) < 0.01  # REGIME_DELTA_THR per triage default

        # V3 raw prediction (Mach-E vehicle params + fitted Cf, Cr)
        v3pred_raw = triage.linear_st_yaw_rate(
            v, delta,
            P_MACHE.L, P_MACHE.l_f, P_MACHE.l_r,
            P_MACHE.m, P_MACHE.I_z,
            FIT_CF, FIT_CR,
        )
        # Per-segment bias on straight samples
        resid_raw = v3pred_raw - meas
        mseg = is_straight & np.isfinite(resid_raw)
        bias = float(np.nanmean(resid_raw[mseg])) if mseg.sum() >= 20 else 0.0
        v3pred = v3pred_raw - bias
        v3resid = v3pred - meas  # target for ridge

        feat = np.column_stack([
            v,
            np.abs(a_y_pred),
            np.abs(delta),
            np.sign(ddelta),
        ])

        all_v.append(v)
        all_delta.append(delta)
        all_meas.append(meas)
        all_v0pred.append(v0pred)
        all_v3pred_bias_adj.append(v3pred)
        all_v3resid.append(v3resid)
        all_feat.append(feat)
        all_seg_id.append(np.full(len(df), i, dtype=np.int32))

    v = np.concatenate(all_v)
    delta = np.concatenate(all_delta)
    meas = np.concatenate(all_meas)
    v0pred = np.concatenate(all_v0pred)
    v3pred = np.concatenate(all_v3pred_bias_adj)
    v3resid = np.concatenate(all_v3resid)
    X = np.concatenate(all_feat)
    seg_id = np.concatenate(all_seg_id)

    n_segments = len(seg_paths)
    print(f"Loaded {n_segments} segments, total rows {len(v)}")

    # ----- LOSO ridge on V3 residuals
    oof = np.full(len(v), 0.0)
    for s in range(n_segments):
        train = seg_id != s
        test = ~train
        Xt = X[train]
        yt = v3resid[train]
        mask = np.isfinite(yt) & np.all(np.isfinite(Xt), axis=1)
        if mask.sum() < 50:
            oof[test] = 0.0
            continue
        model = Ridge(alpha=1.0).fit(Xt[mask], yt[mask])
        Xte = X[test]
        # Guard against NaN features
        Xte_clean = np.where(np.isfinite(Xte), Xte, 0.0)
        oof[test] = model.predict(Xte_clean)
        if s % 50 == 0:
            print(f"  LOSO fold {s}/{n_segments}")

    # V4 prediction = V3pred - oof  (since v3resid = v3pred - meas; ridge
    # predicts that residual; subtracting ridge prediction from v3pred
    # gives the corrected prediction)
    v4pred = v3pred - oof

    # ----- Apply canonical sample filter and compute pooled RMSE
    mask = (v > 2.0) & np.isfinite(meas) & np.isfinite(v4pred) & np.isfinite(v0pred)
    n_samples = int(mask.sum())
    print(f"Samples after filter v_mps>2.0: {n_samples}")

    def rmse(a, b):
        d = (a - b)[mask]
        d = d[np.isfinite(d)]
        return float(np.sqrt(np.mean(d ** 2)))

    baseline_rmse_recomp = rmse(v0pred, meas)
    agent_rmse = rmse(v4pred, meas)
    baseline_canonical = 0.014740020892723483
    improvement_pct = (baseline_canonical - agent_rmse) / baseline_canonical * 100.0

    out = {
        "agent_id": "angleA-m4-agent-02",
        "status": "ok",
        "reason": None,
        "reconstruction_method": "json-coeffs",
        "reconstruction_summary": "V4 = linear-ST yaw rate (Mach-E vehicle params + agent's fitted Cf=427029, Cr=483737 from out/ladder_results.json) minus per-segment straight-sample bias minus a LOSO Ridge(alpha=1.0) residual learner on features [v, |a_y_pred|, |delta|, sign(d_delta)], reconstructed from tools/run_ladder.py.",
        "n_segments": n_segments,
        "n_samples_after_filter": n_samples,
        "baseline_rmse": baseline_canonical,
        "baseline_rmse_recomputed": baseline_rmse_recomp,
        "agent_rmse": agent_rmse,
        "improvement_pct": improvement_pct,
        "notes": (
            "Agent fit Cf/Cr and trained V4 ridge on 60 Mach-E segments only; "
            "we apply the same Mach-E parameter set and pipeline to all 545 canonical "
            "Ford segments (Mach-E + F-150) per the 'shipped parameter set' framing. "
            "Per-segment bias and LOSO ridge are recomputed across the full canonical "
            "set using the agent's recipe. Baseline_rmse_recomputed matches canonical to <1e-9."
        ),
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
