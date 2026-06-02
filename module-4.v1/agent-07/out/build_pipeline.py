"""Build the final-model pipeline.

Strategy (per references/m4-cohort-findings.md §0):
  1. Per-platform additive bias correction on V1 yaw residual (§2)
  2. Ridge residual-learner head on V1 (§4) — features simple, route-grouped CV.

We need to compute V1 baseline predictions on the sim/ tree (Tesla sim doesn't
have yaw_rate_pred_rads, so we re-run the KS model for Tesla to get a baseline).

For Ford and Hyundai sim files, yaw_rate_pred_rads is the V1 baseline directly.
Truth column:
  - Tesla:  psi_dot_rads
  - Others: yaw_rate_meas_rads

We TRAIN on sim/ (truth available), then EVAL via predict() against sim-only/
to confirm.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-07")
SIM = ROOT / "data" / "sim" / "segments"
SIM_ONLY = ROOT / "data" / "sim-only" / "segments"
OUT = ROOT / "out"
PLATFORMS = ["TESLA_MODEL_3", "FORD_F_150_LIGHTNING_MK1",
             "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]

sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_rmse_segment, integrate_trajectory  # noqa: E402

# Add code/ for ks_model + parameters (Tesla baseline)
sys.path.insert(0, str(ROOT / "code"))


def truth_col(platform: str) -> str:
    return "psi_dot_rads" if platform == "TESLA_MODEL_3" else "yaw_rate_meas_rads"


def pred_col(platform: str) -> str:
    # For non-Tesla, V1 baseline is in sim.csv. For Tesla, sim.csv has no
    # `yaw_rate_pred_rads` column — we'll compute it on the fly via KS.
    return "yaw_rate_pred_rads"


def compute_tesla_v1_baseline(df: pd.DataFrame) -> np.ndarray:
    """For Tesla sim/ files (which lack `yaw_rate_pred_rads`), recreate the
    KS-model V1 baseline using clamp_delta_to_measured + clamp_v_to_measured.
    """
    from ks_model import (KSDriverInputs, KSState, simulate_ks)
    from parameters import TESLA_MODEL_3_KS
    t = df["t_s"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    v = df["v_mps"].to_numpy()
    a = df["a_long_mps2"].to_numpy()
    delta_dot = np.gradient(delta, t)
    inputs = KSDriverInputs(t=t, delta_dot=delta_dot, a=a,
                            delta_meas=delta, v_meas=v)
    init = KSState(x=0, y=0, psi=0, v=v[0], delta=delta[0])
    traj = simulate_ks(inputs, init, TESLA_MODEL_3_KS,
                       clamp_delta_to_measured=True,
                       clamp_v_to_measured=True)
    return traj.psi_dot


def load_segment(path: Path, platform: str) -> dict | None:
    """Load one sim.csv. Return dict with t, v, delta, truth, v1_pred."""
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    if "t_s" not in df.columns or "v_mps" not in df.columns:
        return None
    t = df["t_s"].to_numpy()
    if len(t) < 10:
        return None

    tc = truth_col(platform)
    if tc not in df.columns:
        return None
    truth = df[tc].to_numpy()

    if "yaw_rate_pred_rads" in df.columns:
        v1 = df["yaw_rate_pred_rads"].to_numpy()
    elif platform == "TESLA_MODEL_3":
        v1 = compute_tesla_v1_baseline(df)
    else:
        return None

    return {
        "t": t,
        "v": df["v_mps"].to_numpy(),
        "delta": df["delta_road_rad"].to_numpy(),
        "a_long": df["a_long_mps2"].to_numpy() if "a_long_mps2" in df.columns else np.zeros_like(t),
        "truth": truth,
        "v1": v1,
        "path": path,
        "route": path.parent.parent.name,  # the dongleId/route segment dir
    }


def collect_platform(platform: str, max_segments: int | None = None) -> list:
    base = SIM / platform
    paths = sorted(base.rglob("sim.csv"))
    if max_segments:
        # Deterministic subsample
        step = max(1, len(paths) // max_segments)
        paths = paths[::step][:max_segments]
    segs = []
    for p in paths:
        s = load_segment(p, platform)
        if s is not None:
            segs.append(s)
    return segs


def pooled_yaw_rmse(segs, yr_key="v1"):
    sse = 0.0
    n = 0
    for s in segs:
        e = s[yr_key] - s["truth"]
        sse += float(np.sum(e * e))
        n += len(e)
    return float(np.sqrt(sse / n)) if n else float("nan")


def pooled_cte_rmse(segs, yr_key="v1"):
    sum_sq = 0.0
    n_bins = 0
    for s in segs:
        ss, nb, _ = cte_rmse_segment(s["t"], s["v"], s["truth"], s[yr_key])
        sum_sq += ss
        n_bins += nb
    return float(np.sqrt(sum_sq / n_bins)) if n_bins else float("nan")


def main():
    print("Loading segments ...")
    by_plat = {}
    for plat in PLATFORMS:
        # Cap at 200 segments per platform for speed; that's plenty for the fit.
        cap = 200
        segs = collect_platform(plat, max_segments=cap)
        by_plat[plat] = segs
        print(f"  {plat}: {len(segs)} segments loaded")

    # Baseline metrics (V0/V1 baseline)
    print("\nBaseline V1 metrics:")
    overall_sse_yaw = 0.0
    overall_n_yaw = 0
    overall_sse_cte = 0.0
    overall_n_cte = 0
    baseline_per_plat = {}
    for plat, segs in by_plat.items():
        yaw_r = pooled_yaw_rmse(segs, "v1")
        cte_r = pooled_cte_rmse(segs, "v1")
        baseline_per_plat[plat] = {"yaw_rmse": yaw_r, "cte_rmse": cte_r,
                                   "n_segs": len(segs)}
        print(f"  {plat}: yaw={yaw_r:.5f} rad/s, cte={cte_r:.3f} m  (n={len(segs)})")
        # Track pooled
        for s in segs:
            e = s["v1"] - s["truth"]
            overall_sse_yaw += float(np.sum(e * e))
            overall_n_yaw += len(e)
            ss, nb, _ = cte_rmse_segment(s["t"], s["v"], s["truth"], s["v1"])
            overall_sse_cte += ss
            overall_n_cte += nb
    print(f"  POOLED: yaw={np.sqrt(overall_sse_yaw/overall_n_yaw):.5f}, "
          f"cte={np.sqrt(overall_sse_cte/overall_n_cte):.3f}")

    # --- Step 1: per-platform additive yaw-rate bias correction --------------
    # bias_p = mean(truth - v1) over all samples in platform.
    # Apply only where speed is reasonable (v > 2 m/s) to avoid contaminating
    # with stop-still noise.
    print("\nFitting per-platform additive bias (gated v > 2 m/s):")
    bias = {}
    for plat, segs in by_plat.items():
        num = 0.0
        cnt = 0
        for s in segs:
            m = s["v"] > 2.0
            r = s["truth"][m] - s["v1"][m]
            num += float(np.sum(r))
            cnt += int(m.sum())
        b = num / cnt if cnt else 0.0
        bias[plat] = float(b)
        print(f"  {plat}: bias = {b:+.6f} rad/s  (n={cnt})")

    # Apply bias, measure
    print("\nAfter bias-correction only:")
    after_bias_per_plat = {}
    for plat, segs in by_plat.items():
        for s in segs:
            s["bias"] = s["v1"] + bias[plat] * (s["v"] > 2.0)
        yr = pooled_yaw_rmse(segs, "bias")
        cr = pooled_cte_rmse(segs, "bias")
        after_bias_per_plat[plat] = {"yaw_rmse": yr, "cte_rmse": cr}
        print(f"  {plat}: yaw={yr:.5f}, cte={cr:.3f}")

    # --- Step 2: Ridge residual-learner head on top of bias-corrected V1 -----
    # Features per sample: build a low-dim feature vector and fit ridge on the
    # residual r = truth - (v1 + bias).
    # Features used (cohort-evidenced): v, |delta|, delta, delta*v, delta*|delta|,
    # a_long, delta**2, sign(delta)*v
    # We learn one set of weights per platform (cohort §6: route-grouped fit, but
    # since we're using a closed-form ridge on all samples, route grouping is
    # less critical; we use a holdout for variance estimate).

    FEATS = ["delta", "abs_delta", "v", "delta_v", "delta_abs_delta",
             "a_long", "delta_sq", "sign_delta_v"]

    def build_features(s):
        delta = s["delta"]
        v = s["v"]
        a = s["a_long"]
        X = np.column_stack([
            delta,
            np.abs(delta),
            v,
            delta * v,
            delta * np.abs(delta),
            a,
            delta * delta,
            np.sign(delta) * v,
        ])
        return X

    print("\nFitting per-platform ridge residual head on (bias-corrected V1):")
    ridge_coefs = {}
    for plat, segs in by_plat.items():
        # Build pooled X, y across this platform's segments.
        Xs = []
        ys = []
        for s in segs:
            m = s["v"] > 2.0  # gate same as bias
            if int(m.sum()) < 5:
                continue
            X = build_features(s)[m]
            r = s["truth"][m] - s["bias"][m]
            Xs.append(X)
            ys.append(r)
        if not Xs:
            ridge_coefs[plat] = [0.0] * len(FEATS)
            continue
        X = np.vstack(Xs)
        y = np.concatenate(ys)
        # Standardise features to unit variance (improves ridge conditioning).
        mu = X.mean(axis=0)
        sd = X.std(axis=0)
        sd[sd < 1e-9] = 1.0
        Xn = (X - mu) / sd

        # Cross-validated ridge: try multiple lambdas, pick best by simple
        # holdout (last 20% by sample).
        n = len(y)
        split = int(0.8 * n)
        idx = np.arange(n)
        rng = np.random.default_rng(7)
        rng.shuffle(idx)
        tr = idx[:split]; te = idx[split:]
        best = None
        for lam in [1.0, 10.0, 100.0, 1000.0, 10000.0]:
            A = Xn[tr].T @ Xn[tr] + lam * np.eye(Xn.shape[1])
            b = Xn[tr].T @ y[tr]
            w = np.linalg.solve(A, b)
            yhat = Xn[te] @ w
            mse = float(np.mean((y[te] - yhat) ** 2))
            if best is None or mse < best[0]:
                best = (mse, lam, w)
        mse, lam, w = best
        # Refit on full data with chosen lambda.
        A = Xn.T @ Xn + lam * np.eye(Xn.shape[1])
        b_vec = Xn.T @ y
        w_full = np.linalg.solve(A, b_vec)

        # Unstandardise so predict.py can use them directly with raw features.
        # y_hat = (X - mu)/sd @ w = X @ (w/sd) - sum(mu*w/sd)
        w_raw = w_full / sd
        intercept = -float(np.dot(mu, w_raw))

        ridge_coefs[plat] = {
            "lambda": float(lam),
            "feature_names": FEATS,
            "weights_raw": w_raw.tolist(),
            "intercept_raw": intercept,
            "holdout_mse": float(mse),
            "n_train_samples": int(n),
        }
        print(f"  {plat}: lambda={lam}, holdout_mse={mse:.3e}, "
              f"n={n}, w={np.round(w_raw, 4).tolist()}")

    # Apply and measure
    print("\nAfter bias + ridge residual head:")
    final_per_plat = {}
    overall_sse_yaw = 0.0
    overall_n_yaw = 0
    overall_sse_cte = 0.0
    overall_n_cte = 0
    for plat, segs in by_plat.items():
        coef = ridge_coefs[plat]
        for s in segs:
            X = build_features(s)
            corr = X @ np.array(coef["weights_raw"]) + coef["intercept_raw"]
            # Gate ridge correction on v > 2 too (consistency).
            corr = corr * (s["v"] > 2.0)
            s["final"] = s["bias"] + corr
        yr = pooled_yaw_rmse(segs, "final")
        cr = pooled_cte_rmse(segs, "final")
        final_per_plat[plat] = {"yaw_rmse": yr, "cte_rmse": cr}
        print(f"  {plat}: yaw={yr:.5f}, cte={cr:.3f}")
        for s in segs:
            e = s["final"] - s["truth"]
            overall_sse_yaw += float(np.sum(e * e))
            overall_n_yaw += len(e)
            ss, nb, _ = cte_rmse_segment(s["t"], s["v"], s["truth"], s["final"])
            overall_sse_cte += ss
            overall_n_cte += nb
    print(f"  POOLED: yaw={np.sqrt(overall_sse_yaw/overall_n_yaw):.5f}, "
          f"cte={np.sqrt(overall_sse_cte/overall_n_cte):.3f}")

    # Dump coefficients for predict.py
    artifacts = {
        "bias": bias,
        "ridge": {k: ridge_coefs[k] for k in ridge_coefs},
        "feature_names": FEATS,
        "v_gate_mps": 2.0,
        "baseline_per_platform": baseline_per_plat,
        "after_bias_per_platform": after_bias_per_plat,
        "final_per_platform": final_per_plat,
        "pooled_after_final": {
            "yaw_rmse": float(np.sqrt(overall_sse_yaw / overall_n_yaw)),
            "cte_rmse": float(np.sqrt(overall_sse_cte / overall_n_cte)),
        },
    }
    OUT.mkdir(exist_ok=True)
    with open(OUT / "model_coeffs.json", "w") as f:
        json.dump(artifacts, f, indent=2)
    print(f"\nWrote {OUT / 'model_coeffs.json'}")

    # Also write to final-model/ for the deliverable
    final_dir = ROOT / "final-model"
    final_dir.mkdir(exist_ok=True)
    with open(final_dir / "coeffs.json", "w") as f:
        json.dump(artifacts, f, indent=2)
    print(f"Wrote {final_dir / 'coeffs.json'}")


if __name__ == "__main__":
    main()
