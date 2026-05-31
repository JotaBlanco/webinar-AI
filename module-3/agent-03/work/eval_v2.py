"""Score V2 vs V0 and V1."""
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

PARAMS_V1 = json.loads((ROOT / "work" / "params.json").read_text())
PARAMS_V2 = json.loads((ROOT / "work" / "params_v2.json").read_text())


def first_order_lag(yr_ss, t, tau):
    if tau <= 1e-6:
        return yr_ss.copy()
    y = np.empty_like(yr_ss)
    y[0] = yr_ss[0]
    dt = np.diff(t)
    a = np.exp(-dt / tau)
    for k in range(len(dt)):
        y[k + 1] = a[k] * y[k] + (1.0 - a[k]) * yr_ss[k + 1]
    return y


def predict_v0(sim_df, platform):
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy(float)}, index=sim_df.index)


def predict_v1(sim_df, platform):
    if platform not in PARAMS_V1:
        return predict_v0(sim_df, platform)
    p = PARAMS_V1[platform]
    delta = sim_df["delta_road_rad"].to_numpy(float)
    v = sim_df["v_mps"].to_numpy(float)
    t = sim_df["t_s"].to_numpy(float)
    delta_eff = p["g"] * delta + p["delta0"]
    yr_ss = v * delta_eff / (p["L_eff"] + p["K_us"] * v * v)
    yr = first_order_lag(yr_ss, t, p["tau"])
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)


def predict_v2(sim_df, platform):
    if platform not in PARAMS_V2:
        return predict_v0(sim_df, platform)
    p = PARAMS_V2[platform]
    delta = sim_df["delta_road_rad"].to_numpy(float)
    v = sim_df["v_mps"].to_numpy(float)
    t = sim_df["t_s"].to_numpy(float)
    delta_eff = p["g0"] * delta + p["g2"] * delta * np.abs(delta) + p["delta0"]
    K_eff = p["K0"] + p["K1"] * v
    yr_ss = v * delta_eff / (p["L_eff"] + K_eff * v * v)
    yr = first_order_lag(yr_ss, t, p["tau"])
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)


if __name__ == "__main__":
    train, dev = split()

    def summary(name, predict_fn, paths):
        r = score(predict_fn, segment_paths=paths)
        print(f"\n[{name}]")
        print(f"  overall: yaw={r['yaw_rate_rmse']:.5f}  cte={r['cte_rmse']:.2f}m  n_segs={r['n_segments']}")
        for plat, p in r["per_platform"].items():
            print(f"  {plat}: yaw={p['yaw_rate_rmse']:.5f}  cte={p['cte_rmse']:.2f}")
        print(f"  per_regime: {r['per_regime']}")
        return r

    print("======== DEV ========")
    r0d = summary("V0 dev", predict_v0, dev)
    r1d = summary("V1 dev", predict_v1, dev)
    r2d = summary("V2 dev", predict_v2, dev)

    print("\n======== FULL FORD (train+dev) ========")
    r0a = summary("V0 all", predict_v0, None)
    r1a = summary("V1 all", predict_v1, None)
    r2a = summary("V2 all", predict_v2, None)
