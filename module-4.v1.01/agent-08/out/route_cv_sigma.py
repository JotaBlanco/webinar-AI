"""Compute route-grouped CV sigma for the per-platform gain/bias terms."""
import sys, json, math
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-08")
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1

SIM_ROOT = ROOT / "data" / "sim" / "segments"
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
ALLOWLIST=["t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2","accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"]

def list_segments():
    rows=[]
    for plat in PLATFORMS:
        for p in (SIM_ROOT/plat).rglob("sim.csv"):
            rel = p.relative_to(SIM_ROOT/plat).parts
            rows.append({"platform":plat, "route":rel[0], "path":str(p)})
    return pd.DataFrame(rows)

def fit_gb_on(segs, plat):
    XtX=np.zeros((2,2)); Xty=np.zeros(2)
    for _,r in segs.iterrows():
        if r["platform"]!=plat: continue
        df = pd.read_csv(r["path"])
        for c in ("accel_pedal_pct","brake_pressed"):
            if c not in df.columns: df[c]=0
        v1 = predict_v1(df[ALLOWLIST], plat)["yaw_rate_pred_rads"].to_numpy()
        truth = df["yaw_rate_meas_rads"].to_numpy()
        X = np.column_stack([v1, np.ones_like(v1)])
        XtX += X.T@X; Xty += X.T@truth
    return np.linalg.solve(XtX, Xty)

segs = list_segments()
k=5
result={}
rng=np.random.default_rng(0)
for plat in PLATFORMS:
    plat_segs = segs[segs["platform"]==plat]
    routes = plat_segs["route"].unique().tolist()
    rng.shuffle(routes)
    folds = np.array_split(np.arange(len(routes)), k)
    gains=[]; biases=[]
    for fi, val_idx in enumerate(folds):
        val_routes = set(routes[i] for i in val_idx)
        train = segs[~((segs["platform"]==plat)&(segs["route"].isin(val_routes)))]
        beta = fit_gb_on(train, plat)
        gains.append(float(beta[0])); biases.append(float(beta[1]))
    result[plat] = {
        "gain_mean": float(np.mean(gains)),
        "gain_std": float(np.std(gains)),
        "bias_mean": float(np.mean(biases)),
        "bias_std": float(np.std(biases)),
        "route_cv_sigma": float(np.std(biases)),  # bias-term sigma
    }
print(json.dumps(result, indent=2))
with open(ROOT/"out"/"route_cv_sigma.json","w") as f: json.dump(result, f, indent=2)
