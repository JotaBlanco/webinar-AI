"""Lateral-fidelity variant ladder for Mach-E.

V0: baseline residual (yaw_rate_resid_rads as-is from sim.csv)
V1: per-segment IMU yaw-gyro bias removal on straight-line samples
V2: linear single-track steady-state gain with openpilot C_alpha priors (low-v fallback to KS)
V3: linear ST with fitted C_alpha (bounded 50-500 kN/rad), trained on cornering steady samples
V4: ridge residual learner on [v, |a_y|, |delta|, sign(ddelta)], leave-one-segment-out

Same segments, same regime mask across all variants. Marginal drop attributed in lock order.
"""

from __future__ import annotations

import sys
import glob
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

CODE = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-01/code")
sys.path.insert(0, str(CODE))
from parameters import MACH_E  # noqa

PLAT = "FORD_MUSTANG_MACH_E_MK1"
DATA_ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-01/data/sim/segments") / PLAT
N_SEG_LIMIT = 60       # keep runtime reasonable
V_MIN = 2.0            # ST fallback to KS below this speed
DELTA_STRAIGHT = 0.01  # |delta_road| straight cutoff [rad]
DDELTA_TRANSIENT = 0.05  # |dδ/dt| cutoff [rad/s]


def load_segments(limit: int) -> list[tuple[str, pd.DataFrame]]:
    paths = sorted(glob.glob(str(DATA_ROOT / "**" / "sim.csv"), recursive=True))[:limit]
    out = []
    for p in paths:
        try:
            df = pd.read_csv(p)
            if len(df) < 200:
                continue
            out.append((p, df))
        except Exception as e:
            print(f"skip {p}: {e}", file=sys.stderr)
    return out


def regime_mask(df: pd.DataFrame, dt: float = 0.02) -> dict[str, np.ndarray]:
    d = df["delta_road_rad"].values
    ddot = np.gradient(d, dt)
    abs_d = np.abs(d)
    straight = abs_d < DELTA_STRAIGHT
    cornering = ~straight
    transient = cornering & (np.abs(ddot) >= DDELTA_TRANSIENT)
    steady = cornering & ~transient
    return {"straight": straight, "steady": steady, "transient": transient,
            "ddot": ddot, "cornering": cornering}


def rmse(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x**2))) if len(x) else float("nan")


def st_gain(v: np.ndarray, delta: np.ndarray, p, C_af: float, C_ar: float) -> np.ndarray:
    """ψ̇ = v·δ / (L·(1 + K_us·v²)) with KS fallback at v<V_MIN."""
    K_us = p.m * (p.l_r * C_ar - p.l_f * C_af) / (p.L**2 * C_af * C_ar)
    out = np.empty_like(v)
    lowv = v < V_MIN
    # KS fallback
    out[lowv] = (v[lowv] / p.L) * np.tan(delta[lowv])
    out[~lowv] = v[~lowv] * delta[~lowv] / (p.L * (1.0 + K_us * v[~lowv]**2))
    return out


def fit_C_alpha_ratio(v: np.ndarray, delta: np.ndarray, yaw_meas: np.ndarray, p) -> tuple[float, float]:
    """Re-fit C_α treating front/rear ratio fixed but scale free, bounded [50k, 500k].

    We fit a single understeer gradient K_us by least-squares on cornering steady samples:
      yaw_meas ≈ v·δ / (L·(1 + K_us·v²))
    Then back out C_α scaled to keep openpilot ratio.
    """
    # only use samples where prediction is well-defined
    mask = (v >= V_MIN) & (np.abs(delta) > DELTA_STRAIGHT)
    if mask.sum() < 50:
        return p.C_alpha_f, p.C_alpha_r
    vs = v[mask]; ds = delta[mask]; ys = yaw_meas[mask]
    # nonlinear in K_us; solve via 1D grid + golden-section refine
    def loss(K):
        pred = vs * ds / (p.L * (1.0 + K * vs**2))
        return float(np.mean((pred - ys)**2))
    Ks = np.linspace(-0.02, 0.02, 401)
    best_K = Ks[int(np.argmin([loss(K) for K in Ks]))]
    # refine
    lo, hi = best_K - 1e-4, best_K + 1e-4
    for _ in range(40):
        m1 = lo + (hi - lo) / 3
        m2 = hi - (hi - lo) / 3
        if loss(m1) < loss(m2):
            hi = m2
        else:
            lo = m1
    K_us_fit = 0.5 * (lo + hi)
    # invert K_us with ratio fixed: scale both C_a by s, K_us scales as 1/s
    s = (p.m * (p.l_r * p.C_alpha_r - p.l_f * p.C_alpha_f) /
         (p.L**2 * p.C_alpha_f * p.C_alpha_r)) / K_us_fit if abs(K_us_fit) > 1e-9 else 1.0
    s = max(0.1, min(5.0, s))  # sanity clip
    Caf = p.C_alpha_f * s
    Car = p.C_alpha_r * s
    Caf = float(np.clip(Caf, 50_000, 500_000))
    Car = float(np.clip(Car, 50_000, 500_000))
    return Caf, Car


def main():
    t0 = time.time()
    segs = load_segments(N_SEG_LIMIT)
    print(f"loaded {len(segs)} segments")
    p = MACH_E

    # Concatenate, keeping segment indices for LOSO
    frames = []
    seg_ids = []
    for sid, (path, df) in enumerate(segs):
        df = df.copy()
        df["_seg"] = sid
        frames.append(df)
        seg_ids.append(path)
    big = pd.concat(frames, ignore_index=True)

    v = big["v_mps"].values
    delta = big["delta_road_rad"].values
    yaw_meas = big["yaw_rate_meas_rads"].values
    yaw_pred_v0 = big["yaw_rate_pred_rads"].values  # KS prediction already in CSV
    a_lat_meas = big["a_lat_meas_mps2"].values
    seg = big["_seg"].values

    # Build per-row regime
    masks = {"straight": np.zeros(len(big), dtype=bool),
             "steady": np.zeros(len(big), dtype=bool),
             "transient": np.zeros(len(big), dtype=bool)}
    ddot_all = np.zeros(len(big))
    for sid in range(len(segs)):
        idx = np.where(seg == sid)[0]
        sub = big.iloc[idx]
        m = regime_mask(sub)
        masks["straight"][idx] = m["straight"]
        masks["steady"][idx] = m["steady"]
        masks["transient"][idx] = m["transient"]
        ddot_all[idx] = m["ddot"]

    # Sign sanity
    corn = masks["steady"] | masks["transient"]
    sign_corr = float(np.corrcoef(delta[corn], yaw_meas[corn])[0, 1])
    print(f"sign_corr corn(delta, yaw_meas) = {sign_corr:+.3f} (should be > 0)")

    # ----- V0 baseline -----
    resid_v0 = yaw_pred_v0 - yaw_meas

    # ----- V1 per-segment IMU bias on straight samples -----
    yaw_pred_v1 = yaw_pred_v0.copy()
    for sid in range(len(segs)):
        idx_seg = (seg == sid)
        idx_str = idx_seg & masks["straight"]
        if idx_str.sum() > 20:
            bias = float(np.mean(yaw_meas[idx_str] - yaw_pred_v0[idx_str]))
        else:
            bias = 0.0
        # Treat bias as IMU offset on meas: equivalently shift pred up by bias
        yaw_pred_v1[idx_seg] = yaw_pred_v0[idx_seg] + bias
    resid_v1 = yaw_pred_v1 - yaw_meas

    # ----- V2 linear ST with prior C_alpha -----
    yaw_pred_v2_st = st_gain(v, delta, p, p.C_alpha_f, p.C_alpha_r)
    # Apply V1 per-segment bias on top (cumulative)
    yaw_pred_v2 = yaw_pred_v2_st.copy()
    for sid in range(len(segs)):
        idx_seg = (seg == sid)
        idx_str = idx_seg & masks["straight"]
        if idx_str.sum() > 20:
            bias = float(np.mean(yaw_meas[idx_str] - yaw_pred_v2_st[idx_str]))
        else:
            bias = 0.0
        yaw_pred_v2[idx_seg] = yaw_pred_v2_st[idx_seg] + bias
    resid_v2 = yaw_pred_v2 - yaw_meas

    # ----- V3 linear ST with fitted C_alpha (scale openpilot ratio) -----
    fit_mask = masks["steady"]
    Caf, Car = fit_C_alpha_ratio(v[fit_mask], delta[fit_mask], yaw_meas[fit_mask], p)
    print(f"V3 fitted C_af={Caf:.0f}, C_ar={Car:.0f} (prior {p.C_alpha_f:.0f}/{p.C_alpha_r:.0f})")
    pegged_f = abs(Caf - 500_000) < 1.0 or abs(Caf - 50_000) < 1.0
    pegged_r = abs(Car - 500_000) < 1.0 or abs(Car - 50_000) < 1.0
    yaw_pred_v3_st = st_gain(v, delta, p, Caf, Car)
    yaw_pred_v3 = yaw_pred_v3_st.copy()
    for sid in range(len(segs)):
        idx_seg = (seg == sid)
        idx_str = idx_seg & masks["straight"]
        if idx_str.sum() > 20:
            bias = float(np.mean(yaw_meas[idx_str] - yaw_pred_v3_st[idx_str]))
        else:
            bias = 0.0
        yaw_pred_v3[idx_seg] = yaw_pred_v3_st[idx_seg] + bias
    resid_v3 = yaw_pred_v3 - yaw_meas

    # ----- V4 ridge residual learner, LOSO -----
    feat = np.column_stack([v, np.abs(a_lat_meas), np.abs(delta), np.sign(ddot_all)])
    # standardise per LOSO fold
    yaw_pred_v4 = yaw_pred_v3.copy()
    from numpy.linalg import lstsq
    lam = 10.0
    for sid in range(len(segs)):
        train = (seg != sid)
        test = (seg == sid)
        X_tr = feat[train]
        # standardise
        mu = X_tr.mean(0); sd = X_tr.std(0) + 1e-9
        X_tr_s = (X_tr - mu) / sd
        X_tr_aug = np.column_stack([np.ones(len(X_tr_s)), X_tr_s])
        r_tr = resid_v3[train]  # try to LEARN residual then subtract
        # ridge
        A = X_tr_aug.T @ X_tr_aug + lam * np.eye(X_tr_aug.shape[1])
        A[0, 0] -= lam  # don't regularise intercept
        b = X_tr_aug.T @ r_tr
        w = np.linalg.solve(A, b)
        X_te = feat[test]
        X_te_s = (X_te - mu) / sd
        X_te_aug = np.column_stack([np.ones(len(X_te_s)), X_te_s])
        r_hat = X_te_aug @ w
        yaw_pred_v4[test] = yaw_pred_v3[test] - r_hat
    resid_v4 = yaw_pred_v4 - yaw_meas

    # ----- scoring -----
    variants = [("V0_baseline", resid_v0),
                ("V1_imu_bias", resid_v1),
                ("V2_ST_prior", resid_v2),
                ("V3_ST_fit",   resid_v3),
                ("V4_ridge_LOSO", resid_v4)]
    regimes = ["overall", "straight", "steady", "transient"]
    def reg_mask(name):
        if name == "overall":
            return np.ones(len(big), dtype=bool)
        return masks[name]

    table = {}
    for name, r in variants:
        row = {}
        for rg in regimes:
            m = reg_mask(rg)
            row[rg] = rmse(r[m])
        table[name] = row

    # marginal drops
    prev = table["V0_baseline"]
    drops = {}
    for name, _ in variants[1:]:
        cur = table[name]
        drops[name] = {rg: prev[rg] - cur[rg] for rg in regimes}
        prev = cur

    overall_v0 = table["V0_baseline"]["overall"]
    overall_last = table["V4_ridge_LOSO"]["overall"]
    total_drop = overall_v0 - overall_last
    sum_marginals = sum(drops[n]["overall"] for n in [v[0] for v in variants[1:]])
    consistency = abs(sum_marginals - total_drop) / max(abs(total_drop), 1e-9)

    out_path = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-01/out/ladder.json")
    out_path.write_text(json.dumps({
        "platform": PLAT,
        "n_segments": len(segs),
        "n_samples": int(len(big)),
        "sign_corr_corn_delta_yawmeas": sign_corr,
        "regime_counts": {rg: int(reg_mask(rg).sum()) for rg in regimes},
        "table_rmse": table,
        "marginal_drops": drops,
        "total_drop_overall": total_drop,
        "sum_marginals_overall": sum_marginals,
        "consistency_ratio": consistency,
        "C_alpha_fit": {"C_af": Caf, "C_ar": Car, "pegged_f": pegged_f, "pegged_r": pegged_r,
                        "prior_C_af": p.C_alpha_f, "prior_C_ar": p.C_alpha_r},
        "runtime_s": time.time() - t0,
    }, indent=2))
    print(f"wrote {out_path}")
    # also print summary
    print("\nRMSE [rad/s] by regime:")
    cols = "{:<18} {:>10} {:>10} {:>10} {:>10}".format
    print(cols("variant", *regimes))
    for name, _ in variants:
        print(cols(name, *[f"{table[name][rg]:.5f}" for rg in regimes]))
    print("\nMarginal drops (overall):")
    for n in [v[0] for v in variants[1:]]:
        print(f"  {n}: {drops[n]['overall']:+.5f}")
    print(f"Total V0→V4 drop: {total_drop:+.5f}  sum marginals: {sum_marginals:+.5f}  "
          f"consistency: {consistency*100:.1f}%")


if __name__ == "__main__":
    main()
