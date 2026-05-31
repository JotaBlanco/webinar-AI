"""Fit per-platform bicycle coeffs against yaw+cte. Train on small sample, dev on
another for sanity. Save to coeffs.json."""
import sys, os, json, random
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-01")
sys.path.insert(0, str(ROOT / "skills" / "fit-model"))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
os.chdir(ROOT)

import numpy as np
from fit import fit, format_fit_summary  # type: ignore


def _per_segment_delta0(sim_df, fallback=0.0, yr_thresh=0.02, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    if "yaw_rate_pred_rads" in sim_df.columns:
        yr_proxy = sim_df["yaw_rate_pred_rads"].to_numpy()
        mask = (np.abs(yr_proxy) < yr_thresh) & (v > v_thresh)
    else:
        mask = (sim_df["delta_road_rad"].abs() < 0.005) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def make_factory(use_per_seg):
    def factory(platform, coeffs):
        g = coeffs["g"]
        L_eff = coeffs["L_eff"]
        K_us = coeffs["K_us"]
        tau = coeffs["tau"]
        delta0_fb = coeffs.get("delta0", 0.0)

        def predict(sim_df):
            if use_per_seg.get(platform, False):
                delta0 = _per_segment_delta0(sim_df, fallback=delta0_fb)
            else:
                delta0 = delta0_fb
            delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * g
            v = sim_df["v_mps"].to_numpy()
            yr_ss = v * delta / (L_eff + K_us * v * v)
            t = sim_df["t_s"].to_numpy()
            dt = np.diff(t, prepend=t[0])
            alpha = dt / (tau + dt)
            yr = np.empty_like(yr_ss)
            yr[0] = yr_ss[0]
            for i in range(1, len(yr)):
                yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
            return yr
        return predict
    return factory


# Discover segments per platform
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
random.seed(0)

train_segs = {}
dev_segs = {}
for plat in PLATFORMS:
    segs = sorted(Path("data/sim/segments").glob(f"{plat}/**/sim.csv"))
    random.shuffle(segs)
    # Reserve ~20% as dev. Hyundai has 800 — use 60 train, 20 dev for speed.
    if plat == "HYUNDAI_IONIQ_5":
        train_segs[plat] = segs[:60]
        dev_segs[plat] = segs[60:80]
    else:
        # Ford platforms have 175/240 — use 50 train, 20 dev
        train_segs[plat] = segs[:50]
        dev_segs[plat] = segs[50:70]
    print(f"{plat}: {len(train_segs[plat])} train, {len(dev_segs[plat])} dev")

use_per_seg = {
    "FORD_F_150_LIGHTNING_MK1": False,
    "FORD_MUSTANG_MACH_E_MK1": True,
    "HYUNDAI_IONIQ_5": True,
}

init = {
    "FORD_F_150_LIGHTNING_MK1": {
        "g": 0.863, "L_eff": 3.26, "K_us": 0.00350, "tau": 0.060, "delta0": 0.00133,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "g": 0.891, "L_eff": 2.22, "K_us": 0.00202, "tau": 0.069, "delta0": -0.0001,
    },
    "HYUNDAI_IONIQ_5": {
        "g": 0.9, "L_eff": 2.9, "K_us": 0.0025, "tau": 0.065, "delta0": 0.0,
    },
}

bounds = {
    plat: {
        "g": (0.5, 1.5),
        "L_eff": (1.5, 5.0),
        "K_us": (0.0, 0.02),
        "tau": (0.0, 0.3),
        "delta0": (-0.05, 0.05),
    }
    for plat in PLATFORMS
}

# Flatten to a single set of train/dev paths — fit-model takes a dict
factory = make_factory(use_per_seg)

result = fit(
    factory, init,
    train_segments=train_segs,
    dev_segments=dev_segs,
    objective="yaw_plus_cte",
    cte_weight=1.0,
    bounds=bounds,
    max_iter=80,
    verbose=True,
)
print(format_fit_summary(result))

coeffs_out = result["coeffs"]
# Add per-segment flag
for plat, c in coeffs_out.items():
    c["use_per_segment_delta0"] = use_per_seg.get(plat, False)
with open("out/coeffs_v2.json", "w") as f:
    json.dump(coeffs_out, f, indent=2)
print("\nSaved:", coeffs_out)
