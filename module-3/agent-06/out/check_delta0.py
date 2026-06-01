"""How often does per-segment δ₀ fall back on Mach-E and Ioniq?"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-06")


def per_seg_d0(delta_road, v, thresh, vthr=5.0, minrows=50):
    mask = (np.abs(delta_road) < thresh) & (v > vthr)
    if int(mask.sum()) < minrows:
        return None, int(mask.sum())
    return float(np.median(delta_road[mask])), int(mask.sum())


for platform in ["FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5", "FORD_F_150_LIGHTNING_MK1"]:
    base = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(p for p in base.glob("*/**/sim.csv") if p.is_file())[:200]
    falls = 0
    used = 0
    d0s = []
    for p in paths:
        df = pd.read_csv(p, usecols=lambda c: c in {"delta_road_rad", "v_mps"})
        d0, n = per_seg_d0(df["delta_road_rad"].to_numpy(), df["v_mps"].to_numpy(), 0.005)
        if d0 is None:
            falls += 1
        else:
            used += 1
            d0s.append(d0)
    d0s = np.array(d0s)
    print(f"{platform}: {len(paths)} segs, used={used}, fallback={falls}, "
          f"d0 median={np.median(d0s) if used else float('nan'):+.5f} "
          f"std={d0s.std() if used else float('nan'):.5f} "
          f"p10={np.percentile(d0s,10) if used else float('nan'):+.5f} "
          f"p90={np.percentile(d0s,90) if used else float('nan'):+.5f}")
