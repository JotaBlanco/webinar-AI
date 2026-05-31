"""Fit per-platform coefficients for the lateral fidelity model.

Model shape (per platform): polynomial g(δ) = g0 + g2·δ² + per-segment δ₀
from straight-driving rows, steady-state yaw rate with K_us understeer,
first-order lag with τ.

Tesla: V0 passthrough — no truth.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-04")
sys.path.insert(0, str(ROOT / "skills" / "fit-model"))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))

from fit import fit, format_fit_summary  # noqa: E402
from score import score, format_summary  # noqa: E402


# --- model -----------------------------------------------------------------

def _per_segment_delta0(sim_df: pd.DataFrame, fallback: float,
                        ax_thresh: float = 0.3, v_thresh: float = 5.0,
                        min_rows: int = 50) -> float:
    """Estimate δ₀ from rows where vehicle is driving straight. Input-only."""
    if "a_lat_meas_mps2" not in sim_df.columns:
        # a_lat_meas_mps2 is NOT in the allowlist — derive from V0 yaw + v
        # We'll use yaw_rate_pred_rads as a proxy (V0 lateral accel via v*yr).
        # In the worked example a_lat_meas is needed; in sim-only it's not
        # available. Fall back to delta-based straight detector.
        return _per_segment_delta0_fallback(sim_df, fallback, v_thresh, min_rows)
    mask = (sim_df["a_lat_meas_mps2"].abs() < ax_thresh) & (sim_df["v_mps"] > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def _per_segment_delta0_fallback(sim_df: pd.DataFrame, fallback: float,
                                 v_thresh: float = 5.0, min_rows: int = 50) -> float:
    """Backup straight detector when a_lat_meas isn't available.

    Use the V0 baseline yaw-rate prediction: small |yr_pred| <=> straight.
    """
    if "yaw_rate_pred_rads" not in sim_df.columns:
        return fallback
    v = sim_df["v_mps"].to_numpy()
    yr = sim_df["yaw_rate_pred_rads"].to_numpy()
    # |a_lat_proxy| = |v * yr_pred| < 0.3 m/s²
    a_lat_proxy = np.abs(v * yr)
    mask = (a_lat_proxy < 0.3) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(sim_df.loc[mask, "delta_road_rad"].to_numpy()))


def make_predict(platform_params: dict):
    """Return predict(sim_df, platform) using the supplied PLATFORM_PARAMS."""
    def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
        if platform not in platform_params:
            # Tesla / unknown — V0 passthrough
            if "yaw_rate_pred_rads" in sim_df.columns:
                return pd.DataFrame(
                    {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                    index=sim_df.index,
                )
            return pd.DataFrame(
                {"yaw_rate_pred_rads": np.zeros(len(sim_df))}, index=sim_df.index
            )
        p = platform_params[platform]
        if p.get("use_per_segment_delta0", False):
            delta0 = _per_segment_delta0_fallback(sim_df, fallback=p["delta0_fallback"])
        else:
            delta0 = p["delta0"]
        delta_in = sim_df["delta_road_rad"].to_numpy() - delta0
        # polynomial steering scale: g_eff(δ) = g0 + g2·δ²
        g_eff = p["g0"] + p.get("g2", 0.0) * delta_in * delta_in
        delta = delta_in * g_eff
        v = sim_df["v_mps"].to_numpy()
        yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
        t = sim_df["t_s"].to_numpy()
        dt = np.diff(t, prepend=t[0])
        tau = max(p["tau"], 1e-4)
        alpha = dt / (tau + dt)
        yr = np.empty_like(yr_ss)
        yr[0] = yr_ss[0]
        for i in range(1, len(yr)):
            yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
    return predict


# --- fit factory -----------------------------------------------------------

# Per-platform: use_per_segment_delta0 hardcoded by platform (Mach-E ON,
# Lightning OFF per the worked example).
PLATFORM_USE_SEG_D0 = {
    "FORD_MUSTANG_MACH_E_MK1": True,
    "FORD_F_150_LIGHTNING_MK1": False,
    "HYUNDAI_IONIQ_5": True,  # default ON; flip if bias spread is tight
}


def predict_factory(platform: str, coeffs: dict):
    """Return a callable(sim_df) -> ndarray for the fitter."""
    use_seg = PLATFORM_USE_SEG_D0.get(platform, False)

    def cb(sim_df: pd.DataFrame) -> np.ndarray:
        if use_seg:
            delta0 = _per_segment_delta0_fallback(sim_df, fallback=coeffs["delta0"])
        else:
            delta0 = coeffs["delta0"]
        delta_in = sim_df["delta_road_rad"].to_numpy() - delta0
        g_eff = coeffs["g0"] + coeffs.get("g2", 0.0) * delta_in * delta_in
        delta = delta_in * g_eff
        v = sim_df["v_mps"].to_numpy()
        L_eff = max(coeffs["L_eff"], 0.5)
        yr_ss = v * delta / (L_eff + coeffs["K_us"] * v * v)
        t = sim_df["t_s"].to_numpy()
        dt = np.diff(t, prepend=t[0])
        tau = max(coeffs["tau"], 1e-4)
        alpha = dt / (tau + dt)
        yr = np.empty_like(yr_ss)
        yr[0] = yr_ss[0]
        for i in range(1, len(yr)):
            yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
        return yr

    return cb


def main():
    seg_root = ROOT / "data" / "sim" / "segments"
    all_segs = sorted(seg_root.glob("*/**/sim.csv"))
    print(f"Total segments: {len(all_segs)}")
    by_plat: dict[str, list] = {}
    for p in all_segs:
        plat = p.resolve().parents[3].name
        by_plat.setdefault(plat, []).append(p)
    for plat, segs in by_plat.items():
        print(f"  {plat}: {len(segs)} segs")

    # Route-grouped train/dev split per platform: hold out 1 route per platform
    train_segs, dev_segs = [], []
    rng = np.random.default_rng(42)
    for plat, segs in by_plat.items():
        if plat == "TESLA_MODEL_3":
            continue
        routes = {}
        for s in segs:
            route = s.resolve().parents[1].name
            routes.setdefault(route, []).append(s)
        route_names = sorted(routes.keys())
        # hold out ~25% of routes
        n_dev = max(1, len(route_names) // 4)
        dev_routes = list(rng.choice(route_names, size=n_dev, replace=False))
        for r in route_names:
            if r in dev_routes:
                dev_segs.extend(routes[r])
            else:
                train_segs.extend(routes[r])
        print(f"  {plat}: {len(route_names)} routes, {n_dev} held out")
    print(f"Train: {len(train_segs)} segs   Dev: {len(dev_segs)} segs")

    # Initial coeffs from the worked example
    initial = {
        "FORD_F_150_LIGHTNING_MK1": {
            "delta0": 0.00133,
            "g0": 0.863,
            "g2": 0.0,
            "L_eff": 3.26,
            "K_us": 0.00350,
            "tau": 0.060,
        },
        "FORD_MUSTANG_MACH_E_MK1": {
            "delta0": -0.0001,  # used as fallback
            "g0": 0.891,
            "g2": 0.0,
            "L_eff": 2.22,
            "K_us": 0.00202,
            "tau": 0.069,
        },
        "HYUNDAI_IONIQ_5": {
            "delta0": 0.0,
            "g0": 0.9,
            "g2": 0.0,
            "L_eff": 3.0,
            "K_us": 0.003,
            "tau": 0.065,
        },
    }

    bounds = {
        "FORD_F_150_LIGHTNING_MK1": {
            "delta0": (-0.02, 0.02),
            "g0":     (0.5, 1.5),
            "g2":     (-2.0, 2.0),
            "L_eff":  (2.5, 4.5),
            "K_us":   (0.0, 0.015),
            "tau":    (0.005, 0.300),
        },
        "FORD_MUSTANG_MACH_E_MK1": {
            "delta0": (-0.02, 0.02),
            "g0":     (0.5, 1.5),
            "g2":     (-2.0, 2.0),
            "L_eff":  (1.5, 3.5),
            "K_us":   (0.0, 0.015),
            "tau":    (0.005, 0.300),
        },
        "HYUNDAI_IONIQ_5": {
            "delta0": (-0.02, 0.02),
            "g0":     (0.5, 1.5),
            "g2":     (-2.0, 2.0),
            "L_eff":  (1.8, 4.0),
            "K_us":   (0.0, 0.015),
            "tau":    (0.005, 0.300),
        },
    }

    # Stage 1: fit yaw-only (cheaper, gets the steering/understeer parameters right)
    print("\n=== Stage 1: fit yaw RMSE ===")
    r1 = fit(
        predict_factory, initial, train_segments=train_segs,
        objective="yaw", dev_segments=dev_segs,
        bounds=bounds, method="L-BFGS-B", max_iter=200,
        verbose=False,
    )
    print(format_fit_summary(r1))

    # Stage 2: re-fit with yaw_plus_cte starting from stage 1
    print("\n=== Stage 2: fit yaw_plus_cte (warm-started) ===")
    init2 = r1["coeffs"]
    r2 = fit(
        predict_factory, init2, train_segments=train_segs,
        objective="yaw_plus_cte", dev_segments=dev_segs,
        bounds=bounds, method="L-BFGS-B", max_iter=200,
        cte_weight=1.0, verbose=False,
    )
    print(format_fit_summary(r2))

    # Build platform_params dict for final predict
    platform_params = {}
    for plat, c in r2["coeffs"].items():
        platform_params[plat] = {
            "use_per_segment_delta0": PLATFORM_USE_SEG_D0.get(plat, False),
            "delta0_fallback": c["delta0"],
            "delta0": c["delta0"],
            "g0": c["g0"],
            "g2": c["g2"],
            "L_eff": c["L_eff"],
            "K_us": c["K_us"],
            "tau": c["tau"],
        }

    # Score baseline V0 first
    def v0_predict(sim_df, platform):
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )

    print("\n=== V0 baseline score (all data) ===")
    r_v0 = score(v0_predict)
    print(f"V0 yaw_rate_rmse: {r_v0['yaw_rate_rmse']:.6f}   cte_rmse: {r_v0['cte_rmse']:.4f}")
    for plat, m in r_v0["per_platform"].items():
        print(f"  {plat}: yaw={m['yaw_rate_rmse']:.5f}  cte={m['cte_rmse']:.3f}")

    # Score our model
    print("\n=== Fitted model score (all data) ===")
    predict_fn = make_predict(platform_params)
    r = score(predict_fn)
    print(f"yaw_rate_rmse: {r['yaw_rate_rmse']:.6f}   cte_rmse: {r['cte_rmse']:.4f}")
    for plat, m in r["per_platform"].items():
        print(f"  {plat}: yaw={m['yaw_rate_rmse']:.5f}  cte={m['cte_rmse']:.3f} bias={m['yaw_residual_mean']:+.5f}")

    # Score on dev only
    print("\n=== Fitted model score on DEV ===")
    r_dev = score(predict_fn, segment_paths=dev_segs)
    print(f"yaw_rate_rmse: {r_dev['yaw_rate_rmse']:.6f}   cte_rmse: {r_dev['cte_rmse']:.4f}")
    for plat, m in r_dev["per_platform"].items():
        print(f"  {plat}: yaw={m['yaw_rate_rmse']:.5f}  cte={m['cte_rmse']:.3f}")

    out_path = ROOT / "out" / "platform_params.json"
    out_path.write_text(json.dumps(platform_params, indent=2))
    print(f"\nWrote {out_path}")

    # Save the V0 vs fitted summary
    summary = {
        "v0": {
            "yaw_rate_rmse": r_v0["yaw_rate_rmse"],
            "cte_rmse": r_v0["cte_rmse"],
            "per_platform": {p: {"yaw": m["yaw_rate_rmse"], "cte": m["cte_rmse"]}
                             for p, m in r_v0["per_platform"].items()},
        },
        "fitted": {
            "yaw_rate_rmse": r["yaw_rate_rmse"],
            "cte_rmse": r["cte_rmse"],
            "per_platform": {p: {"yaw": m["yaw_rate_rmse"], "cte": m["cte_rmse"]}
                             for p, m in r["per_platform"].items()},
        },
        "dev": {
            "yaw_rate_rmse": r_dev["yaw_rate_rmse"],
            "cte_rmse": r_dev["cte_rmse"],
        },
    }
    (ROOT / "out" / "fit_summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
