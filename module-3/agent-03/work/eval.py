"""Score the fitted physical model against V0 on dev."""
import sys, os, json
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-03")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))
sys.path.insert(0, str(ROOT / "_shared"))

import numpy as np
import pandas as pd
from split import split
from score import score

PARAMS = json.loads((ROOT / "work" / "params.json").read_text())


def first_order_lag(yr_ss: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    if tau <= 1e-6:
        return yr_ss.copy()
    y = np.empty_like(yr_ss)
    y[0] = yr_ss[0]
    dt = np.diff(t)
    a = np.exp(-dt / tau)
    for k in range(len(dt)):
        y[k + 1] = a[k] * y[k] + (1.0 - a[k]) * yr_ss[k + 1]
    return y


def predict_v1(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in PARAMS:
        # Tesla fallback to V0
        return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy(float)}, index=sim_df.index)
    p = PARAMS[platform]
    delta = sim_df["delta_road_rad"].to_numpy(float)
    v = sim_df["v_mps"].to_numpy(float)
    t = sim_df["t_s"].to_numpy(float)
    delta_eff = p["g"] * delta + p["delta0"]
    yr_ss = v * delta_eff / (p["L_eff"] + p["K_us"] * v * v)
    yr_pred = first_order_lag(yr_ss, t, p["tau"])
    return pd.DataFrame({"yaw_rate_pred_rads": yr_pred}, index=sim_df.index)


if __name__ == "__main__":
    train, dev = split()
    print("=== V1 (per-platform KS+US+lag) ON DEV ===")
    res_dev = score(predict_v1, segment_paths=dev)
    print({k: v for k, v in res_dev.items() if k not in ("per_platform", "per_regime")})
    print("per_platform:", res_dev["per_platform"])
    print("per_regime:", res_dev["per_regime"])

    print("\n=== V1 ON FULL FORD SET ===")
    res = score(predict_v1)
    print({k: v for k, v in res.items() if k not in ("per_platform", "per_regime")})
    print("per_platform:", res["per_platform"])
    print("per_regime:", res["per_regime"])
