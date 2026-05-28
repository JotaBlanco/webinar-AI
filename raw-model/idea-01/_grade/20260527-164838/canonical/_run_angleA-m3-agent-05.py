"""Canonical eval for angleA-m3-agent-05.

Agent's favourite: V4 = V3 (linear-ST with fit Cα) + per-segment yaw bias
(straight-line mean) + LOSO ridge residual learner on
[v, |a_y|, |δ|, sign(δ̇)].

Agent only fitted Cα on Mach-E. For the 545-segment canonical eval (Mach-E +
F-150), we use the agent's shipped fitted Cα values for ALL segments (this is
literally the parameter set they shipped). Per-platform L, l_f, l_r, m, I_z
come from PARAM_BY_PLATFORM (the same source the agent used). Per-segment
straight-line yaw bias and LOSO ridge are computed across the full 545-segment
canonical pool.

Sample filter: v_mps > 2.0 (canonical).
Truth: yaw_rate_meas_rads.
"""
from __future__ import annotations
import sys, glob, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI")
AGENT = ROOT / "webinar-angle-A" / "module-3" / "agent-05"
sys.path.insert(0, str(AGENT / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(AGENT / "code"))

import triage  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402

GLOBS = [
    "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
]
SAMPLE_FILTER_V_MIN = 2.0
TRUTH = "yaw_rate_meas_rads"
BASELINE_COL = "yaw_rate_pred_rads"

# Agent's "shipped" Cα fit values (from out/ladder_results.json), fit on Mach-E
C_AF_FIT = 312267.28348696255
C_AR_FIT = 318879.98923199973

# -------- Step 1: collect segments and stream-load --------
paths = []
for g in GLOBS:
    paths.extend(sorted(glob.glob(str(ROOT / g), recursive=True)))
print(f"Found {len(paths)} canonical segments", file=sys.stderr)

REQ_COLS = ["t_s", "v_mps", "delta_road_rad",
            "yaw_rate_meas_rads", "yaw_rate_pred_rads", "a_y_pred_mps2"]

def platform_of(path: str) -> str:
    if "FORD_MUSTANG_MACH_E_MK1" in path:
        return "FORD_MUSTANG_MACH_E_MK1"
    if "FORD_F_150_LIGHTNING_MK1" in path:
        return "FORD_F_150_LIGHTNING_MK1"
    raise ValueError(path)

# Single pass: build a slim dataframe with V3 prediction + features.
parts = []
for i, p in enumerate(paths):
    try:
        df = pd.read_csv(p, usecols=REQ_COLS)
    except Exception as e:
        print(f"skip {p}: {e}", file=sys.stderr)
        continue
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=REQ_COLS)
    if df.empty:
        continue
    plat = platform_of(p)
    P = PARAM_BY_PLATFORM[plat]

    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    meas = df[TRUTH].to_numpy()
    base = df[BASELINE_COL].to_numpy()
    a_y = df["a_y_pred_mps2"].to_numpy()
    t = df["t_s"].to_numpy()

    # V3 linear-ST prediction with platform geometry + agent's Mach-E fit Cα
    st_pred = triage.linear_st_yaw_rate(v, delta, P.L, P.l_f, P.l_r,
                                        P.m, P.I_z, C_AF_FIT, C_AR_FIT)
    v3_resid_raw = st_pred - meas

    # Regime mask (same thresholds the agent used)
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt <= 0, 0.02, dt)
    ddelta = np.gradient(delta) / dt
    abs_delta = np.abs(delta)
    abs_ddelta = np.abs(ddelta)
    is_straight = abs_delta < 0.01

    # Per-segment yaw bias = mean residual on straight samples
    if is_straight.any():
        bias = float(np.mean(v3_resid_raw[is_straight]))
    else:
        bias = 0.0
    v3_resid = v3_resid_raw - bias
    # The V3 prediction with bias removed:
    v3_pred_corr = st_pred - bias

    parts.append(pd.DataFrame({
        "seg": p,
        "v": v,
        "delta": delta,
        "abs_ay": np.abs(a_y),
        "sign_ddelta": np.sign(ddelta),
        "meas": meas,
        "baseline_pred": base,
        "v3_pred": v3_pred_corr,
        "v3_resid": v3_resid,
    }))
    if (i + 1) % 50 == 0:
        print(f"  loaded {i+1}/{len(paths)}", file=sys.stderr)

full = pd.concat(parts, ignore_index=True)
print(f"Total rows (pre-filter): {len(full):,}", file=sys.stderr)

# -------- Step 2: LOSO ridge residual learner --------
from sklearn.linear_model import Ridge

segs = full["seg"].unique()
seg_idx = {s: i for i, s in enumerate(segs)}
seg_codes = full["seg"].map(seg_idx).to_numpy()

X = np.column_stack([
    full["v"].to_numpy(),
    full["abs_ay"].to_numpy(),
    np.abs(full["delta"].to_numpy()),
    full["sign_ddelta"].to_numpy(),
])
y = full["v3_resid"].to_numpy()

oof = np.full(len(full), np.nan)
for s, idx in enumerate(segs):
    test = seg_codes == s
    train = ~test
    if train.sum() < 100 or test.sum() < 1:
        oof[test] = 0.0
        continue
    model = Ridge(alpha=1.0).fit(X[train], y[train])
    oof[test] = model.predict(X[test])

# Agent V4 prediction
v4_pred = full["v3_pred"].to_numpy() + oof

# -------- Step 3: apply sample filter and compute pooled RMSE --------
mask = full["v"].to_numpy() > SAMPLE_FILTER_V_MIN
truth = full["meas"].to_numpy()
base_pred = full["baseline_pred"].to_numpy()

base_err = base_pred[mask] - truth[mask]
agent_err = v4_pred[mask] - truth[mask]

baseline_rmse_recomputed = float(np.sqrt(np.mean(base_err ** 2)))
agent_rmse = float(np.sqrt(np.mean(agent_err ** 2)))

CANONICAL_BASELINE = 0.014740020892723483
improvement_pct = (CANONICAL_BASELINE - agent_rmse) / CANONICAL_BASELINE * 100

n_samples = int(mask.sum())
n_segments = int(len(segs))

print(f"n_segments={n_segments} n_samples={n_samples}", file=sys.stderr)
print(f"baseline_recomputed={baseline_rmse_recomputed} canonical={CANONICAL_BASELINE}",
      file=sys.stderr)
print(f"agent_rmse={agent_rmse} improvement_pct={improvement_pct:.3f}", file=sys.stderr)

out = {
    "agent_id": "angleA-m3-agent-05",
    "status": "ok",
    "reason": None,
    "reconstruction_method": "json-coeffs",
    "reconstruction_summary": (
        "Re-ran the agent's V4 stack (their declared best): linear-ST yaw rate "
        "with the agent's saved fit Cα (Cαf=312267, Cαr=318880 N/rad from "
        "out/ladder_results.json) plus per-segment straight-line yaw-bias "
        "correction plus a LOSO Ridge(α=1) residual learner on "
        "[v,|a_y|,|δ|,sign(δ̇)], using per-platform L/l_f/l_r/m/I_z from "
        "PARAM_BY_PLATFORM."
    ),
    "n_segments": n_segments,
    "n_samples_after_filter": n_samples,
    "baseline_rmse": CANONICAL_BASELINE,
    "baseline_rmse_recomputed": baseline_rmse_recomputed,
    "agent_rmse": agent_rmse,
    "improvement_pct": improvement_pct,
    "notes": (
        "Agent's Cα fit (Cαf=312267, Cαr=318880) was tuned on 80 Mach-E "
        "segments only; we apply it to all 545 canonical Ford segments "
        "(315 Mach-E + 230 F-150) — F-150 uses Mach-E-tuned Cα as that is "
        "what the agent shipped, which somewhat undersells F-150 fidelity. "
        "Per-segment yaw bias and LOSO Ridge are computed across the full "
        "canonical pool. Baseline sanity-check matches cached canonical V0 "
        "to <1e-9."
    ),
}

out_path = ROOT / "raw-model/idea-01/_grade/20260527-164838/canonical/angleA-m3-agent-05.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w") as f:
    json.dump(out, f, indent=2)
print(f"wrote {out_path}", file=sys.stderr)
