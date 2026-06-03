"""Fit per-platform yaw-rate gain (and combined gain+bias) atop V1."""
import sys, json, math
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-08")
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))
from v1_baseline import predict_v1
from traj_metrics import cte_rmse_segment

SIM_ROOT = ROOT / "data" / "sim" / "segments"
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
ALLOWLIST = ["t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
             "a_long_mps2", "accel_pedal_pct", "brake_pressed", "yaw_rate_pred_rads"]

def list_segments():
    rows=[]
    for plat in PLATFORMS:
        for p in (SIM_ROOT/plat).rglob("sim.csv"):
            rel = p.relative_to(SIM_ROOT/plat).parts
            rows.append({"platform":plat, "route":rel[0], "path":str(p)})
    return pd.DataFrame(rows)

def load(p):
    df = pd.read_csv(p)
    if "accel_pedal_pct" not in df.columns: df["accel_pedal_pct"]=0.0
    if "brake_pressed" not in df.columns: df["brake_pressed"]=0
    return df

def fit_gain_bias(segments):
    """Solve [g, b] minimising sum (g*v1 + b - truth)^2 per platform."""
    out={}
    for plat, grp in segments.groupby("platform"):
        XtX = np.zeros((2,2)); Xty = np.zeros(2); n=0
        for _,r in grp.iterrows():
            df = load(r["path"])
            v1 = predict_v1(df[ALLOWLIST], plat)["yaw_rate_pred_rads"].to_numpy()
            truth = df["yaw_rate_meas_rads"].to_numpy()
            X = np.column_stack([v1, np.ones_like(v1)])
            XtX += X.T@X; Xty += X.T@truth; n+=len(v1)
        beta = np.linalg.solve(XtX, Xty)
        out[plat] = {"gain": float(beta[0]), "bias": float(beta[1])}
    return out

def score(pred_fn, segments):
    ysq=0; yn=0; csq=0; cn=0
    for _,r in segments.iterrows():
        df = load(r["path"])
        truth = df["yaw_rate_meas_rads"].to_numpy()
        pred = pred_fn(df[ALLOWLIST], r["platform"])["yaw_rate_pred_rads"].to_numpy()
        ysq += float(((pred-truth)**2).sum()); yn += len(pred)
        sq,nb,_ = cte_rmse_segment(df["t_s"].to_numpy(), df["v_mps"].to_numpy(), truth, pred)
        csq+=sq; cn+=nb
    return {"yaw_rmse": math.sqrt(ysq/yn), "cte_rmse": math.sqrt(csq/cn)}

def make_pred_gb(gb):
    def predict(sim_df, platform):
        out = predict_v1(sim_df, platform).copy()
        if platform in gb:
            g = gb[platform]["gain"]; b = gb[platform]["bias"]
            out["yaw_rate_pred_rads"] = g * out["yaw_rate_pred_rads"].to_numpy() + b
        return out
    return predict

def route_grouped_cv(segments, fit_fn, make_fn, k=5, seed=0):
    keys = segments.groupby(["platform","route"]).size().reset_index().drop(columns=0)
    keys = keys.sample(frac=1, random_state=seed).reset_index(drop=True)
    folds = np.array_split(np.arange(len(keys)), k)
    scores=[]
    for fi, val_idx in enumerate(folds):
        val_keys = set(map(tuple, keys.iloc[val_idx][["platform","route"]].values.tolist()))
        train_mask = ~segments.set_index(["platform","route"]).index.isin(val_keys)
        train = segments[train_mask].reset_index(drop=True)
        val = segments[~train_mask].reset_index(drop=True)
        coefs = fit_fn(train)
        scores.append(score(make_fn(coefs), val))
    yaws=[s["yaw_rmse"] for s in scores]
    ctes=[s["cte_rmse"] for s in scores]
    return {"yaw_mean":float(np.mean(yaws)),"yaw_std":float(np.std(yaws)),
            "cte_mean":float(np.mean(ctes)),"cte_std":float(np.std(ctes))}

if __name__=="__main__":
    segs = list_segments()
    gb = fit_gain_bias(segs)
    print("gain/bias per platform:", json.dumps(gb, indent=2))
    res = score(make_pred_gb(gb), segs)
    print("V1+gain+bias (in-sample):", json.dumps(res, indent=2))
    cv = route_grouped_cv(segs, fit_gain_bias, make_pred_gb)
    print("V1+gain+bias CV:", json.dumps(cv, indent=2))
    with open(ROOT/"out"/"gain_bias.json","w") as f:
        json.dump({"gain_bias":gb, "in_sample":res, "cv":cv}, f, indent=2)
