"""Score the final-model against V0 on all (or sampled) Ford segments."""
import sys, importlib.util, json, random
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from evaluate import (
    load_segments, yaw_rate_rmse, distance_resample_cte, FORD_PLATFORMS,
)

# Dynamically import final-model/predict.py:predict
spec = importlib.util.spec_from_file_location("final_predict",
                                              ROOT / "final-model" / "predict.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
predict = mod.predict


def eval_pool(platform: str, segs):
    yr_v0=[]; yr_vf=[]; cte_v0=[]; cte_vf=[]
    for s in segs:
        df = pd.read_csv(ROOT / "data" / "sim" / s["csv_path"])
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        t = df["t_s"].to_numpy(); v = df["v_mps"].to_numpy()
        yt = df["yaw_rate_meas_rads"].to_numpy()
        yp0 = df["yaw_rate_pred_rads"].to_numpy()
        out = predict(df, platform)
        ypf = out["yaw_rate_pred_rads"].to_numpy()
        mask = np.isfinite(yt) & np.isfinite(v) & np.isfinite(yp0) & np.isfinite(ypf)
        if mask.sum() < 50: continue
        t=t[mask]-t[mask][0]; v=v[mask]; yt=yt[mask]; yp0=yp0[mask]; ypf=ypf[mask]
        yr_v0.append(yaw_rate_rmse(yt, yp0))
        yr_vf.append(yaw_rate_rmse(yt, ypf))
        c0 = distance_resample_cte(t, v, yt, yp0)
        cf = distance_resample_cte(t, v, yt, ypf)
        if np.isfinite(c0): cte_v0.append(c0)
        if np.isfinite(cf): cte_vf.append(cf)
    return {
        "n": len(yr_v0),
        "yaw_v0": float(np.mean(yr_v0)), "yaw_final": float(np.mean(yr_vf)),
        "cte_v0": float(np.mean(cte_v0)) if cte_v0 else float("nan"),
        "cte_final": float(np.mean(cte_vf)) if cte_vf else float("nan"),
    }


if __name__ == "__main__":
    random.seed(0)
    for plat in FORD_PLATFORMS:
        man = json.load(open(ROOT/"data"/"sim"/"segments"/plat/"manifest.json"))
        segs = list(man["segments"]); random.shuffle(segs)
        cut = int(0.6*len(segs))
        test = segs[cut:]
        r = eval_pool(plat, test)
        print(f"[HELD-OUT] {plat}: n={r['n']}")
        print(f"  Yaw RMSE: V0={r['yaw_v0']:.5f}  Final={r['yaw_final']:.5f}  "
              f"({100*(1-r['yaw_final']/r['yaw_v0']):+.1f}%)")
        print(f"  CTE  RMSE: V0={r['cte_v0']:.3f}m  Final={r['cte_final']:.3f}m  "
              f"({100*(1-r['cte_final']/r['cte_v0']):+.1f}%)")
