"""Canonical eval for raw-agent-08.

Reconstructs the agent's favourite V5 model:
  - Per-platform joint fit of (k_sr, d0, K_us) on filter |a_lat_meas|<20  (V4)
  - Per-platform integer-sample lag shift (V5) to minimise RMSE on V4 preds
  - Prediction equation:  psi_dot = v/(L + K_us*v^2) * (k_sr*(delta - d0))

Then evaluates across ALL 545 Ford canonical segments with filter v_mps > 2.0,
applying lag shift WITHIN each segment to avoid edge contamination.
Streams segments and accumulates pooled sum-of-squares.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

DATA_ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/data")
AGENT_ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-08")
OUT_PATH = Path(
    "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/_grade/20260527-164838/canonical/raw-agent-08.json"
)

L_BY_PLAT = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
}
GLOBS = {
    "FORD_F_150_LIGHTNING_MK1": "data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv",
    "FORD_MUSTANG_MACH_E_MK1": "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
}


def rmse(x):
    return float(np.sqrt(np.mean(x ** 2)))


def predict_bicycle_ss(v, delta, L, K_us):
    return v / (L + K_us * v * v) * delta


# === Step 1: Fit per-platform V4 + V5 parameters using the agent's training procedure ===
print("Loading agent's all_ford.parquet for fits...")
df = pd.read_parquet(AGENT_ROOT / "out" / "all_ford.parquet")

params = {}
for plat, L in L_BY_PLAT.items():
    print(f"\nFitting {plat} (L={L})...")
    dfp = df[df["__seg"].str.startswith(plat)].reset_index(drop=True)
    # V1 cleanup: |a_lat|<20
    mask = dfp["a_lat_meas_mps2"].abs() < 20.0
    dfc = dfp[mask]
    v = dfc["v_mps"].values
    delta = dfc["delta_road_rad"].values
    meas = dfc["yaw_rate_meas_rads"].values

    # V4: joint fit k_sr, d0, K_us
    def loss(K):
        c = v / (L + K * v * v)
        X = np.column_stack([c * delta, -c])
        coef, *_ = np.linalg.lstsq(X, meas, rcond=None)
        return rmse(meas - X @ coef)

    res = minimize_scalar(loss, bounds=(-0.02, 0.05), method="bounded",
                          options={"xatol": 1e-7})
    K = float(res.x)
    c = v / (L + K * v * v)
    X = np.column_stack([c * delta, -c])
    coef, *_ = np.linalg.lstsq(X, meas, rcond=None)
    k_sr = float(coef[0])
    d0_eff = float(coef[1])
    d0 = d0_eff / k_sr if abs(k_sr) > 1e-9 else 0.0

    pred4 = predict_bicycle_ss(v, k_sr * (delta - d0), L, K)
    print(f"  V4: k_sr={k_sr:.5f}, d0={d0:.6f} rad, K_us={K:.6f} s^2/m, RMSE={rmse(meas-pred4):.6f}")

    # V5: integer-sample lag shift (per-platform, on the |a_lat|<20 data, pooled across segments
    #     — matches the agent's procedure)
    best_rmse = rmse(meas - pred4)
    best_lag = 0
    for lag in range(-15, 16):  # ±0.30s @ 50Hz
        if lag == 0:
            r = meas - pred4
        elif lag > 0:
            r = meas[lag:] - pred4[:-lag]
        else:
            r = meas[:lag] - pred4[-lag:]
        e = rmse(r)
        if e < best_rmse:
            best_rmse = e
            best_lag = lag
    print(f"  V5: best_lag={best_lag} samples ({best_lag*20} ms), RMSE={best_rmse:.6f}")

    params[plat] = {"L": L, "k_sr": k_sr, "d0": d0, "K_us": K, "lag": int(best_lag)}

print("\nFitted parameters:")
print(json.dumps(params, indent=2))


# === Step 2: Stream through ALL 545 canonical Ford segments, apply per-segment lag ===
print("\nEvaluating on canonical segments (v_mps > 2.0 filter)...")

sse_baseline = 0.0       # sum of (pred_csv - meas)^2 for baseline sanity check
n_baseline = 0
sse_agent = 0.0
n_agent = 0
n_segments = 0

for plat, p in params.items():
    L = p["L"]
    k_sr = p["k_sr"]
    d0 = p["d0"]
    K_us = p["K_us"]
    lag = p["lag"]

    pattern = str(DATA_ROOT / "sim" / "segments" / plat / "**" / "sim.csv")
    files = sorted(glob.glob(pattern, recursive=True))
    print(f"  {plat}: {len(files)} segments, lag={lag}")
    for f in files:
        n_segments += 1
        seg = pd.read_csv(f)
        v = seg["v_mps"].values
        delta = seg["delta_road_rad"].values
        meas = seg["yaw_rate_meas_rads"].values
        pred_csv = seg["yaw_rate_pred_rads"].values

        # Agent's V5 prediction equation
        agent_pred = predict_bicycle_ss(v, k_sr * (delta - d0), L, K_us)

        # Apply per-segment lag shift
        if lag > 0:
            meas_l = meas[lag:]
            agent_l = agent_pred[:-lag] if lag > 0 else agent_pred
            v_l = v[lag:]
        elif lag < 0:
            meas_l = meas[:lag]
            agent_l = agent_pred[-lag:]
            v_l = v[:lag]
        else:
            meas_l = meas
            agent_l = agent_pred
            v_l = v

        # Canonical filter: v_mps > 2.0  (use the speed at the MEASURED row time)
        mask_agent = v_l > 2.0
        r_agent = meas_l[mask_agent] - agent_l[mask_agent]
        sse_agent += float(np.sum(r_agent * r_agent))
        n_agent += int(mask_agent.sum())

        # Baseline sanity-check: pred_csv vs meas, no lag, canonical filter
        mask_b = v > 2.0
        r_b = meas[mask_b] - pred_csv[mask_b]
        sse_baseline += float(np.sum(r_b * r_b))
        n_baseline += int(mask_b.sum())

baseline_rmse_recomputed = float(np.sqrt(sse_baseline / n_baseline))
agent_rmse = float(np.sqrt(sse_agent / n_agent))
baseline_rmse_cached = 0.014740020892723483
improvement_pct = (baseline_rmse_cached - agent_rmse) / baseline_rmse_cached * 100.0

print(f"\nn_segments = {n_segments}")
print(f"n_samples_baseline (no lag) = {n_baseline}")
print(f"n_samples_agent    (lagged) = {n_agent}")
print(f"baseline RMSE (recomputed)  = {baseline_rmse_recomputed:.10f}")
print(f"baseline RMSE (cached)      = {baseline_rmse_cached:.10f}")
print(f"agent    RMSE                = {agent_rmse:.10f}")
print(f"improvement_pct              = {improvement_pct:.4f}%")

notes_bits = []
diff = abs(baseline_rmse_recomputed - baseline_rmse_cached)
if diff > 1e-6:
    notes_bits.append(
        f"baseline_rmse_recomputed differs from cached by {diff:.2e}"
    )
notes_bits.append(
    "Reconstructed by re-running agent's V4 joint-fit + V5 lag-shift procedure "
    "on agent's all_ford.parquet (agent did not persist coefficients); per-platform "
    f"params: F150 k_sr={params['FORD_F_150_LIGHTNING_MK1']['k_sr']:.4f} "
    f"d0={params['FORD_F_150_LIGHTNING_MK1']['d0']:.5f} "
    f"K_us={params['FORD_F_150_LIGHTNING_MK1']['K_us']:.5f} "
    f"lag={params['FORD_F_150_LIGHTNING_MK1']['lag']}; "
    f"MachE k_sr={params['FORD_MUSTANG_MACH_E_MK1']['k_sr']:.4f} "
    f"d0={params['FORD_MUSTANG_MACH_E_MK1']['d0']:.5f} "
    f"K_us={params['FORD_MUSTANG_MACH_E_MK1']['K_us']:.5f} "
    f"lag={params['FORD_MUSTANG_MACH_E_MK1']['lag']}. "
    "V5 lag applied within each segment (no cross-segment leakage). "
    f"n_samples_agent={n_agent} < canonical baseline n=1364925 because the lag "
    "shift drops one sample per segment per platform."
)

result = {
    "agent_id": "raw-agent-08",
    "status": "ok",
    "reason": None,
    "reconstruction_method": "re-ran-script",
    "reconstruction_summary": (
        "Agent's V5 = V4 (per-platform joint fit of steering scale k_sr, zero-offset d0, "
        "and understeer K_us in psi_dot = v/(L+K_us*v^2) * k_sr*(delta-d0)) plus a "
        "per-platform integer-sample lag shift; re-fit on agent's all_ford.parquet "
        "because coefficients were not persisted."
    ),
    "n_segments": n_segments,
    "n_samples_after_filter": n_agent,
    "baseline_rmse": baseline_rmse_cached,
    "baseline_rmse_recomputed": baseline_rmse_recomputed,
    "agent_rmse": agent_rmse,
    "improvement_pct": improvement_pct,
    "notes": " ".join(notes_bits),
}

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_PATH, "w") as f:
    json.dump(result, f, indent=2)
print(f"\nWrote {OUT_PATH}")
