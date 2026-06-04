"""Fit V1 (linear understeer) per platform with a route-grouped train/dev split.

Tesla is excluded from fitting (truth == V0, no signal to learn).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-02")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "fit-model"))
sys.path.insert(0, str(ROOT / "out"))

from score import score, format_summary  # noqa: E402
from fit import fit, format_fit_summary  # noqa: E402
from model_lib import predict_v1, INITIAL_COEFFS_V1, BOUNDS_V1  # noqa: E402

import numpy as np  # noqa: E402

# ---------- Build segment paths ----------
seg_root = ROOT / "data" / "sim" / "segments"
all_seg_paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())


def _platform(p: Path) -> str:
    return p.resolve().parents[3].name


def _route(p: Path) -> str:
    return p.resolve().parents[1].name


# Group by (platform, route)
by_plat_route = defaultdict(list)
for p in all_seg_paths:
    by_plat_route[(_platform(p), _route(p))].append(p)

# Route-grouped split — deterministic — 80/20
rng = np.random.RandomState(42)
train_segments = []
dev_segments = []
routes_by_plat = defaultdict(list)
for (plat, route), segs in by_plat_route.items():
    routes_by_plat[plat].append((route, segs))

for plat, routes in routes_by_plat.items():
    routes_sorted = sorted(routes, key=lambda x: x[0])
    rng.shuffle(routes_sorted)
    n_dev = max(1, len(routes_sorted) // 5)
    dev_routes = routes_sorted[:n_dev]
    train_routes = routes_sorted[n_dev:]
    for _, segs in train_routes:
        train_segments.extend(segs)
    for _, segs in dev_routes:
        dev_segments.extend(segs)

print(f"train: {len(train_segments)} segments, dev: {len(dev_segments)} segments")


# ---------- Predict factory for the fitter ----------
def predict_factory_v1(platform: str, coeffs: dict):
    def cb(sim_df):
        return predict_v1(sim_df, coeffs)
    return cb


# Exclude Tesla from fitting (truth == V0)
initial = {p: c for p, c in INITIAL_COEFFS_V1.items() if p != "TESLA_MODEL_3"}
bounds  = {p: b for p, b in BOUNDS_V1.items() if p != "TESLA_MODEL_3"}

print("\n=== Fitting V1 (yaw objective) ===")
result_yaw = fit(
    predict_factory_v1,
    initial,
    train_segments,
    objective="yaw",
    dev_segments=dev_segments,
    bounds=bounds,
    max_iter=300,
    verbose=False,
)
print(format_fit_summary(result_yaw))

# Save coeffs
out_path = ROOT / "out" / "coeffs_v1_yaw.json"
out_path.write_text(json.dumps(result_yaw["coeffs"], indent=2))
print(f"\nsaved coeffs → {out_path}")


# ---------- Score the V1 fit on the FULL set ----------
def predict_v1_full(sim_df, platform):
    import pandas as pd
    coeffs = result_yaw["coeffs"].get(platform)
    if coeffs is None:
        # Tesla — pass through V0
        yr = sim_df["yaw_rate_pred_rads"].to_numpy()
    else:
        yr = predict_v1(sim_df, coeffs)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)


print("\n=== Scoring V1 on FULL set ===")
s_full = score(predict_v1_full, segment_paths=all_seg_paths)
print(format_summary(s_full, top_n=5))
