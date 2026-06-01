"""Fit V2 with yaw_plus_cte objective — push CTE bias down too."""
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
from model_lib import predict_v2, INITIAL_COEFFS_V2, BOUNDS_V2  # noqa: E402

import numpy as np  # noqa: E402

seg_root = ROOT / "data" / "sim" / "segments"
all_seg_paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())


def _platform(p: Path) -> str:
    return p.resolve().parents[3].name


def _route(p: Path) -> str:
    return p.resolve().parents[1].name


by_plat_route = defaultdict(list)
for p in all_seg_paths:
    by_plat_route[(_platform(p), _route(p))].append(p)

rng = np.random.RandomState(42)
routes_by_plat = defaultdict(list)
for (plat, route), segs in by_plat_route.items():
    routes_by_plat[plat].append((route, segs))

train_segments = []
dev_segments = []
for plat, routes in routes_by_plat.items():
    routes_sorted = sorted(routes, key=lambda x: x[0])
    rng.shuffle(routes_sorted)
    n_dev = max(1, len(routes_sorted) // 5)
    for _, segs in routes_sorted[:n_dev]:
        dev_segments.extend(segs)
    for _, segs in routes_sorted[n_dev:]:
        train_segments.extend(segs)

print(f"train: {len(train_segments)} segments, dev: {len(dev_segments)} segments")


def predict_factory_v2(platform: str, coeffs: dict):
    def cb(sim_df):
        return predict_v2(sim_df, coeffs)
    return cb


# Warm-start from V2 yaw fit
v2_path = ROOT / "out" / "coeffs_v2_yaw.json"
initial = {p: c for p, c in INITIAL_COEFFS_V2.items() if p != "TESLA_MODEL_3"}
bounds  = {p: b for p, b in BOUNDS_V2.items() if p != "TESLA_MODEL_3"}
if v2_path.exists():
    v2_coeffs = json.loads(v2_path.read_text())
    for plat, c in v2_coeffs.items():
        if plat in initial:
            initial[plat] = dict(c)
    print(f"warm-started from V2-yaw coeffs at {v2_path}")

print("\n=== Fitting V2 (yaw_plus_cte objective, cte_weight=2.0) ===")
result = fit(
    predict_factory_v2,
    initial,
    train_segments,
    objective="yaw_plus_cte",
    dev_segments=dev_segments,
    bounds=bounds,
    max_iter=500,
    cte_weight=2.0,
    verbose=False,
)
print(format_fit_summary(result))

out_path = ROOT / "out" / "coeffs_v2_yaw_plus_cte.json"
out_path.write_text(json.dumps(result["coeffs"], indent=2))
print(f"\nsaved coeffs → {out_path}")


def predict_v2_full(sim_df, platform):
    import pandas as pd
    coeffs = result["coeffs"].get(platform)
    if coeffs is None:
        yr = sim_df["yaw_rate_pred_rads"].to_numpy()
    else:
        yr = predict_v2(sim_df, coeffs)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)


print("\n=== Scoring V2(yaw+cte) on FULL set ===")
s_full = score(predict_v2_full, segment_paths=all_seg_paths)
print(format_summary(s_full, top_n=3))
