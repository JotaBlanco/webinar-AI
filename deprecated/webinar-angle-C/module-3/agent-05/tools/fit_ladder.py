#!/usr/bin/env python3
"""fit_ladder.py — V0→V4 variant ladder for lateral yaw-rate prediction.

Per-platform fit; interleaved-5 train/test split (rule 7).
Strict marginal attribution V0→V4. Same regime mask across variants.

Usage:  python3 tools/fit_ladder.py <PLATFORM>
Outputs:
  out/<PLATFORM>__ladder.json  — fitted params, RMSE per variant per regime
  out/<PLATFORM>__variant_sim.csv  — V4 corrected CSV (sample of one segment for schema_check)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REGIME_DELTA_THR = 0.01
REGIME_DDELTA_THR = 0.05


def regime_mask(delta: np.ndarray, t: np.ndarray) -> np.ndarray:
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt <= 0, 0.02, dt)
    ddelta = np.gradient(delta) / dt
    out = np.full(len(delta), "transient", dtype=object)
    out[np.abs(delta) < REGIME_DELTA_THR] = "straight"
    steady = (np.abs(delta) >= REGIME_DELTA_THR) & (np.abs(ddelta) < REGIME_DDELTA_THR)
    out[steady] = "steady"
    return out


def rmse(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(np.sqrt(np.mean(x ** 2))) if x.size else float("nan")


def apply_lag_per_segment(pred: np.ndarray, seg_ids: np.ndarray, dt: float, tau: float) -> np.ndarray:
    """First-order discrete lag y[k] = a*y[k-1] + (1-a)*pred[k], reset per segment."""
    if tau <= 0:
        return pred.copy()
    a = float(np.exp(-dt / tau))
    out = np.empty_like(pred)
    prev_seg = None
    y = 0.0
    for i, (p, s) in enumerate(zip(pred, seg_ids)):
        if s != prev_seg:
            y = p  # initialise at first sample of segment
            prev_seg = s
        else:
            y = a * y + (1.0 - a) * p
        out[i] = y
    return out


def load_platform(platform: str) -> pd.DataFrame:
    data_root = Path("data/sim/segments") / platform
    csvs = sorted(data_root.rglob("sim.csv"))
    if not csvs:
        print(f"no sim.csv under {data_root}", file=sys.stderr)
        sys.exit(2)
    frames = []
    for i, p in enumerate(csvs):
        df = pd.read_csv(p)
        df["__seg__"] = i
        df["__src__"] = str(p)
        frames.append(df)
    return pd.concat(frames, ignore_index=True), csvs


def fit_bias(pred: np.ndarray, meas: np.ndarray, train: np.ndarray) -> float:
    # Minimise sum((pred - b - meas)^2) over b → b = mean(pred - meas) on train
    r = pred[train] - meas[train]
    return float(np.mean(r[np.isfinite(r)]))


def fit_gain(pred: np.ndarray, meas: np.ndarray, b: float, train: np.ndarray) -> float:
    # Minimise sum((k*(pred - b_corrected for static) - meas))^2... we want k on the pred-with-bias-removed.
    # Model: meas ≈ k*(pred - b)  →  k = sum(p'*meas)/sum(p'*p') where p' = pred - b
    p_adj = pred[train] - b
    m = meas[train]
    finite = np.isfinite(p_adj) & np.isfinite(m)
    num = float(np.sum(p_adj[finite] * m[finite]))
    den = float(np.sum(p_adj[finite] * p_adj[finite]))
    return num / den if den > 0 else 1.0


def fit_lag(pred_in: np.ndarray, meas: np.ndarray, seg_ids: np.ndarray, dt: float,
            train: np.ndarray, taus=None) -> tuple[float, float]:
    if taus is None:
        taus = np.concatenate([[0.0], np.linspace(0.02, 0.50, 25)])
    best_tau = 0.0
    best_rmse = float("inf")
    for tau in taus:
        lagged = apply_lag_per_segment(pred_in, seg_ids, dt, float(tau))
        r = lagged[train] - meas[train]
        e = rmse(r)
        if e < best_rmse:
            best_rmse = e
            best_tau = float(tau)
    return best_tau, best_rmse


def rmse_by_regime(resid: np.ndarray, reg: np.ndarray, mask: np.ndarray) -> dict:
    out = {"overall": rmse(resid[mask])}
    for r in ("straight", "steady", "transient"):
        sel = mask & (reg == r)
        out[r] = rmse(resid[sel])
    return out


def main():
    if len(sys.argv) != 2:
        print("usage: fit_ladder.py <PLATFORM>", file=sys.stderr)
        sys.exit(2)
    platform = sys.argv[1]
    big, csvs = load_platform(platform)

    t = big["t_s"].to_numpy()
    delta = big["delta_road_rad"].to_numpy()
    meas = big["yaw_rate_meas_rads"].to_numpy()
    pred0 = big["yaw_rate_pred_rads"].to_numpy()
    seg = big["__seg__"].to_numpy()

    reg = regime_mask(delta, t)
    # Cornering sanity check
    corner = (reg == "steady") | (reg == "transient")
    corr_dy = float(np.corrcoef(delta[corner], meas[corner])[0, 1])

    # Interleaved every-5th sample → train index = i%5 == 0; test = rest
    idx = np.arange(len(big))
    train = (idx % 5 == 0)
    test = ~train

    DT = 0.02  # 50 Hz

    # V0
    resid_v0 = pred0 - meas
    v0_train = rmse_by_regime(resid_v0, reg, train)
    v0_test = rmse_by_regime(resid_v0, reg, test)

    # V1: global bias
    b = fit_bias(pred0, meas, train)
    pred_v1 = pred0 - b
    resid_v1 = pred_v1 - meas
    v1_test = rmse_by_regime(resid_v1, reg, test)

    # V2: gain on (pred - b)
    k = fit_gain(pred0, meas, b, train)
    pred_v2 = k * (pred0 - b)
    resid_v2 = pred_v2 - meas
    v2_test = rmse_by_regime(resid_v2, reg, test)

    # V3: lag on V2's prediction; refit bias after lag is fine but keep order strict — apply lag then no refit.
    tau, _ = fit_lag(pred_v2, meas, seg, DT, train)
    pred_v3 = apply_lag_per_segment(pred_v2, seg, DT, tau)
    resid_v3 = pred_v3 - meas
    v3_test = rmse_by_regime(resid_v3, reg, test)

    # V4: a_y consequence — a_y_pred = v * ψ̇_pred_corrected. Compare to a_lat_meas.
    v = big["v_mps"].to_numpy()
    a_y_meas = big["a_lat_meas_mps2"].to_numpy()
    a_y_pred0 = big["a_y_pred_mps2"].to_numpy()
    a_y_pred_v4 = v * pred_v3
    a_y_resid_v0 = a_y_pred0 - a_y_meas
    a_y_resid_v4 = a_y_pred_v4 - a_y_meas
    a_y = {
        "v0_test": rmse_by_regime(a_y_resid_v0, reg, test),
        "v4_test": rmse_by_regime(a_y_resid_v4, reg, test),
    }

    # marginal attribution (test set, overall RMSE drops)
    marginals = {
        "V0->V1_bias":      v0_test["overall"] - v1_test["overall"],
        "V1->V2_gain":      v1_test["overall"] - v2_test["overall"],
        "V2->V3_lag":       v2_test["overall"] - v3_test["overall"],
    }
    total_drop = v0_test["overall"] - v3_test["overall"]

    out = {
        "platform": platform,
        "n_segments": len(csvs),
        "n_samples": len(big),
        "corr_delta_yawrate_cornering": corr_dy,
        "fit": {"bias_b_rads": b, "gain_k": k, "lag_tau_s": tau, "dt_s": DT},
        "regimes": {
            "thresholds": {"REGIME_DELTA_THR": REGIME_DELTA_THR, "REGIME_DDELTA_THR": REGIME_DDELTA_THR},
            "counts": {r: int(((reg == r) & test).sum()) for r in ("straight", "steady", "transient")},
        },
        "rmse_yawrate_test_rads": {
            "V0_baseline": v0_test,
            "V1_bias":     v1_test,
            "V2_gain":     v2_test,
            "V3_lag":      v3_test,
        },
        "rmse_yawrate_train_rads_V0": v0_train,
        "marginal_drops_overall_rads": marginals,
        "total_drop_V0_to_V3_rads": total_drop,
        "rmse_a_y_test_mps2": a_y,
    }

    out_dir = Path("out")
    out_dir.mkdir(exist_ok=True)
    json_path = out_dir / f"{platform}__ladder.json"
    json_path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))

    # Write a representative variant CSV for schema_check (single segment).
    # Pick the first segment, regenerate the residual columns using V4 corrected predictions.
    seg0_mask = (seg == 0)
    df0 = big.loc[seg0_mask].copy().reset_index(drop=True)
    df0["yaw_rate_pred_rads"] = pred_v3[seg0_mask]
    df0["a_y_pred_mps2"]      = a_y_pred_v4[seg0_mask]
    df0["yaw_rate_resid_rads"] = df0["yaw_rate_pred_rads"] - df0["yaw_rate_meas_rads"]
    df0["a_y_resid_mps2"]      = df0["a_y_pred_mps2"]      - df0["a_lat_meas_mps2"]
    df0 = df0.drop(columns=["__seg__", "__src__"])
    csv_path = out_dir / f"{platform}__variant_sim.csv"
    df0.to_csv(csv_path, index=False)
    print(f"\nwrote {json_path}\nwrote {csv_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
