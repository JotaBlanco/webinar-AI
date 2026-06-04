"""Fit V1 per-platform coefficients for the kinematic-bicycle + understeer + lag
+ per-segment δ₀ model. Recipe from references/anti-patterns.md § Legal cousin.

Fits Mach-E, Lightning, IONIQ-5. Tesla passes through V0.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-01")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "fit-model"))
from score import score, format_summary  # noqa: E402
from fit import fit, format_fit_summary  # noqa: E402


# ---------------------------------------------------------------------------
# The model predict shape (yaw rate only). Closure over (platform, coeffs).
# Uses only allowlist columns: delta_road_rad, v_mps, t_s, yaw_rate_pred_rads.
# ---------------------------------------------------------------------------

def _per_segment_delta0(sim_df, fallback=0.0,
                        yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    """Estimate δ₀ from THIS segment's own straight-driving rows."""
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(pd.Series(sim_df["delta_road_rad"].to_numpy()[mask]).median())


def make_predict(platform: str, p: dict):
    """Returns a callable sim_df -> yaw_rate ndarray.

    Coeffs in p:
      g           gain on steering angle
      L_eff       effective wheelbase (m)
      K_us        understeer coefficient
      tau         first-order lag (s)
      delta0      static steering offset (rad) — used if use_per_segment_delta0=False
      use_per_segment_delta0  (bool)
      delta0_fallback         fallback δ₀ when straight-row gate empty
    """
    use_seg = bool(p.get("use_per_segment_delta0", False))
    delta0_static = float(p.get("delta0", 0.0))
    delta0_fallback = float(p.get("delta0_fallback", 0.0))
    g = float(p["g"])
    L_eff = float(p["L_eff"])
    K_us = float(p["K_us"])
    tau = float(p["tau"])

    def predict(sim_df):
        if use_seg:
            d0 = _per_segment_delta0(sim_df, fallback=delta0_fallback)
        else:
            d0 = delta0_static
        delta = (sim_df["delta_road_rad"].to_numpy() - d0) * g
        v = sim_df["v_mps"].to_numpy()
        yr_ss = v * delta / (L_eff + K_us * v * v)
        t = sim_df["t_s"].to_numpy()
        dt = np.diff(t, prepend=t[0])
        alpha = dt / (tau + dt)
        yr = np.empty_like(yr_ss)
        yr[0] = yr_ss[0]
        for i in range(1, len(yr)):
            yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
        return yr

    return predict


def predict_factory_yaw_only(platform_to_static_coeffs):
    """Returns predict_factory(platform, fit_coeffs) for use with fit-model.

    fit_coeffs contains the optimisation variables (g, L_eff, K_us, tau,
    delta0 if static). Static / non-optimised flags are pulled from
    platform_to_static_coeffs.
    """
    def factory(platform, fit_coeffs):
        static = platform_to_static_coeffs[platform]
        merged = {**static, **fit_coeffs}
        return make_predict(platform, merged)
    return factory


# ---------------------------------------------------------------------------
# Route-grouped split for honest dev scoring.
# ---------------------------------------------------------------------------

def route_grouped_split(segments, dev_frac=0.25, seed=42):
    rng = np.random.RandomState(seed)
    by_route = defaultdict(list)
    for p in segments:
        route = Path(p).resolve().parents[1].name
        by_route[route].append(p)
    routes = sorted(by_route.keys())
    rng.shuffle(routes)
    n_dev = max(1, int(len(routes) * dev_frac))
    dev_routes = set(routes[:n_dev])
    train, dev = [], []
    for r, segs in by_route.items():
        (dev if r in dev_routes else train).extend(segs)
    return train, dev


# ---------------------------------------------------------------------------
# Run fits per platform.
# ---------------------------------------------------------------------------

def main():
    all_segs = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))

    # Filter out Tesla — no truth.
    all_segs = [p for p in all_segs if p.resolve().parents[3].name != "TESLA_MODEL_3"]

    # Bucket by platform, route-split each platform independently.
    by_plat = defaultdict(list)
    for p in all_segs:
        by_plat[p.resolve().parents[3].name].append(p)

    train_by_plat, dev_by_plat = {}, {}
    for plat, segs in by_plat.items():
        tr, dv = route_grouped_split(segs, dev_frac=0.25, seed=42)
        train_by_plat[plat] = tr
        dev_by_plat[plat] = dv
        print(f"  {plat}: {len(tr)} train / {len(dv)} dev segments")

    # Static / non-optimised flags per platform.
    static = {
        "FORD_F_150_LIGHTNING_MK1": {"use_per_segment_delta0": False, "delta0_fallback": 0.0},
        "FORD_MUSTANG_MACH_E_MK1":  {"use_per_segment_delta0": True,  "delta0_fallback": 0.0},
        "HYUNDAI_IONIQ_5":          {"use_per_segment_delta0": True,  "delta0_fallback": 0.0},
    }

    # Initial guesses from the reference recipe.
    init = {
        "FORD_F_150_LIGHTNING_MK1": {
            "g": 0.863, "L_eff": 3.26, "K_us": 0.00350, "tau": 0.060, "delta0": 0.00133,
        },
        "FORD_MUSTANG_MACH_E_MK1": {
            "g": 0.891, "L_eff": 2.22, "K_us": 0.00150, "tau": 0.069,
            # delta0 not used (per-segment on), but we still fit it for fallback symmetry? No —
            # we use delta0_fallback static = 0. Don't include delta0 here.
        },
        "HYUNDAI_IONIQ_5": {
            "g": 0.938, "L_eff": 2.887, "K_us": 0.00289, "tau": 0.062,
        },
    }

    bounds = {
        "FORD_F_150_LIGHTNING_MK1": {
            "g": (0.5, 1.3), "L_eff": (2.0, 5.0), "K_us": (-0.005, 0.02),
            "tau": (0.01, 0.30), "delta0": (-0.02, 0.02),
        },
        "FORD_MUSTANG_MACH_E_MK1": {
            "g": (0.5, 1.3), "L_eff": (1.5, 4.0), "K_us": (-0.005, 0.02),
            "tau": (0.01, 0.30),
        },
        "HYUNDAI_IONIQ_5": {
            "g": (0.5, 1.3), "L_eff": (1.5, 4.0), "K_us": (-0.005, 0.02),
            "tau": (0.01, 0.30),
        },
    }

    factory = predict_factory_yaw_only(static)

    print("\n=== Fit yaw_plus_cte ===")
    res = fit(
        factory, initial_coeffs=init,
        train_segments=train_by_plat,
        dev_segments=dev_by_plat,
        bounds=bounds,
        objective="yaw_plus_cte",
        cte_weight=1.0,
        max_iter=120,
        verbose=False,
    )
    print(format_fit_summary(res))

    # Persist fitted coefficients merged with static flags.
    out = {}
    for plat, c in res["coeffs"].items():
        merged = {**static[plat], **c}
        out[plat] = merged
    # Add Tesla passthrough sentinel.
    out["TESLA_MODEL_3"] = {"passthrough": True}

    coeffs_path = ROOT / "out" / "coeffs_v1.json"
    coeffs_path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {coeffs_path}")

    return out


if __name__ == "__main__":
    main()
