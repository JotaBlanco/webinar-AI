"""Shapley-style attribution over the 3 model levers: offset, understeer, scale.
Lag is tiny so we drop it. Evaluate all 2^3 subsets and average marginal RMSE
reductions over orderings.
"""
from __future__ import annotations
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-08")
L_BY_PLAT = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
}


def rmse(x):
    return float(np.sqrt(np.mean(x ** 2)))


def predict(v, delta, L, use_offset, use_us, use_scale, meas):
    """Fit subset, return resulting RMSE."""
    # Build prediction with linear-in-coefs structure where possible.
    # Effective model: psi_dot = c(v, K_us) * (k_sr*delta - k_sr*d0_eff)
    # where c = v / (L + K_us * v^2).
    # If !us: K_us = 0 -> c = v / L
    # If !scale: k_sr = 1.0 fixed
    # If !offset: d0 = 0 fixed
    if not use_us:
        K_grid = [0.0]
    else:
        # 1-D search
        def inner(K):
            c = v / (L + K * v * v)
            return _fit_inner(c, delta, meas, use_scale, use_offset)
        res = minimize_scalar(inner, bounds=(-0.005, 0.02), method="bounded",
                              options={"xatol": 1e-7})
        return inner(res.x)
    return _fit_inner(v / L, delta, meas, use_scale, use_offset)


def _fit_inner(c, delta, meas, use_scale, use_offset):
    # pred = c * (k_sr * delta - k_sr*d0)  = k_sr*c*delta - (k_sr*d0)*c
    if use_scale and use_offset:
        X = np.column_stack([c * delta, -c])
    elif use_scale and not use_offset:
        X = (c * delta).reshape(-1, 1)
    elif use_offset and not use_scale:
        # k_sr = 1: pred = c*delta - c*d0  => meas - c*delta ~ -c*d0
        # equivalent: lstsq with col -c only on residual
        target = meas - c * delta
        X = (-c).reshape(-1, 1)
        coef, *_ = np.linalg.lstsq(X, target, rcond=None)
        return rmse(target - X @ coef)
    else:
        # no levers: pred = c*delta
        return rmse(meas - c * delta)
    coef, *_ = np.linalg.lstsq(X, meas, rcond=None)
    return rmse(meas - X @ coef)


def main():
    df = pd.read_parquet(ROOT / "out" / "all_ford.parquet")
    levers = ["offset", "us", "scale"]
    all_subsets = []
    for r in range(0, 4):
        for s in itertools.combinations(levers, r):
            all_subsets.append(frozenset(s))

    # Pool both platforms — fit per platform, sum squared errors.
    def rmse_for(subset):
        sse = 0.0
        n = 0
        for plat, L in L_BY_PLAT.items():
            dfp = df[df["__seg"].str.startswith(plat)]
            mask = dfp["a_lat_meas_mps2"].abs() < 20.0
            dfc = dfp[mask]
            v = dfc["v_mps"].values
            delta = dfc["delta_road_rad"].values
            meas = dfc["yaw_rate_meas_rads"].values
            r = predict(v, delta, L, "offset" in subset, "us" in subset,
                        "scale" in subset, meas)
            # convert RMSE back to SSE
            sse += (r ** 2) * len(meas)
            n += len(meas)
        return np.sqrt(sse / n)

    rmse_by_set = {s: rmse_for(s) for s in all_subsets}
    base = rmse_by_set[frozenset()]
    print(f"Empty-set RMSE: {np.degrees(base):.4f} deg/s")
    for s in sorted(all_subsets, key=lambda x: (len(x), sorted(x))):
        print(f"  {sorted(s) or '[]'}: RMSE={np.degrees(rmse_by_set[s]):.4f} deg/s "
              f"(drop from empty: {np.degrees(base - rmse_by_set[s]):.4f})")

    # Shapley: avg marginal contribution over all orderings
    shap = {l: 0.0 for l in levers}
    for perm in itertools.permutations(levers):
        cur = frozenset()
        for l in perm:
            nxt = cur | {l}
            shap[l] += rmse_by_set[cur] - rmse_by_set[nxt]
            cur = nxt
    n_perm = 6
    for l in levers:
        shap[l] /= n_perm
    total = sum(shap.values())
    print("\nShapley attribution of RMSE reduction (deg/s):")
    for l in levers:
        print(f"  {l:8s}: {np.degrees(shap[l]):.4f} deg/s "
              f"({100*shap[l]/total:.1f}% of total)")
    print(f"  TOTAL    : {np.degrees(total):.4f} deg/s")


if __name__ == "__main__":
    main()
