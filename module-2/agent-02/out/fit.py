"""Fit per-platform coefficients for the lateral model.

Model: yaw_rate_pred = scale * v * delta / (L + K * v^2) + bias_per_v

We use train/dev split by route. Train fits K, scale, optional steering-offset.
We also tested per-segment lag but keep model simple.
"""
import sys, json, random
from pathlib import Path
import numpy as np, pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from parameters import PARAM_BY_PLATFORM, TeslaModel3KS

# Platform wheelbase (incl. Hyundai which isn't in code/)
L_BY_PLATFORM = {
    "TESLA_MODEL_3": 2.875,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5": 3.0,  # approximate — will be auto-fit if no truth
}

SIM_ROOT = ROOT / "data" / "sim" / "segments"

def load_route_split(platform, train_frac=0.8, seed=0):
    rng = random.Random(seed)
    plat_dir = SIM_ROOT / platform
    routes = sorted([d.name for d in plat_dir.iterdir() if d.is_dir()])
    rng.shuffle(routes)
    n_train = max(1, int(len(routes) * train_frac))
    train_routes = set(routes[:n_train])
    return train_routes

def gather(platform, route_set, max_segments=200):
    plat_dir = SIM_ROOT / platform
    rows = []
    paths = []
    for route_dir in plat_dir.iterdir():
        if route_dir.name not in route_set:
            continue
        for sub in route_dir.iterdir():
            for idx in sub.iterdir():
                p = idx / "sim.csv"
                if p.exists():
                    paths.append(p)
    random.Random(0).shuffle(paths)
    paths = paths[:max_segments]
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=["t_s","delta_road_rad","v_mps","yaw_rate_meas_rads"])
        except Exception:
            continue
        rows.append(df)
    if not rows:
        return None
    big = pd.concat(rows, ignore_index=True)
    big = big[big["v_mps"] > 2.0].dropna()
    return big

def fit_platform(platform, train_routes):
    df = gather(platform, train_routes)
    if df is None or len(df) < 1000:
        return None
    L = L_BY_PLATFORM.get(platform, 2.9)
    v = df["v_mps"].to_numpy(float)
    d = df["delta_road_rad"].to_numpy(float)
    yr = df["yaw_rate_meas_rads"].to_numpy(float)

    # Model: yr = scale * v * (d - d0) / (L + K * v^2)
    # Fit K, scale, d0
    def model(params):
        K, scale, d0 = params
        return scale * v * (d - d0) / (L + K * v * v)

    def loss(params):
        pred = model(params)
        return float(np.mean((pred - yr) ** 2))

    res = minimize(loss, x0=[0.003, 1.0, 0.0], method="Nelder-Mead",
                   options={"xatol": 1e-6, "fatol": 1e-10, "maxiter": 5000})
    K, scale, d0 = res.x
    rmse_fit = float(np.sqrt(res.fun))
    rmse_base = float(np.sqrt(np.mean((v*d/L - yr) ** 2)))
    return {"L": L, "K": float(K), "scale": float(scale), "d0": float(d0),
            "rmse_fit": rmse_fit, "rmse_base_kinematic": rmse_base,
            "n_samples": int(len(v))}


if __name__ == "__main__":
    out = {}
    for plat in sorted(SIM_ROOT.iterdir()):
        if not plat.is_dir():
            continue
        name = plat.name
        if name == "TESLA_MODEL_3":
            # No truth in our sim — fall back to a sensible default later
            print(f"SKIP {name}: no truth in sim/")
            continue
        train_routes = load_route_split(name)
        coefs = fit_platform(name, train_routes)
        if coefs:
            out[name] = coefs
            print(f"{name}: K={coefs['K']:.5f} scale={coefs['scale']:.4f} d0={coefs['d0']:+.5f}  fit_rmse={coefs['rmse_fit']:.5f}  base={coefs['rmse_base_kinematic']:.5f}  n={coefs['n_samples']}")

    # For Tesla, borrow the median of the others (or just use Mach-E numbers)
    if "FORD_MUSTANG_MACH_E_MK1" in out:
        ref = out["FORD_MUSTANG_MACH_E_MK1"]
        out["TESLA_MODEL_3"] = {"L": 2.875, "K": ref["K"], "scale": ref["scale"], "d0": 0.0,
                                 "rmse_fit": float("nan"), "rmse_base_kinematic": float("nan"),
                                 "n_samples": 0, "borrowed_from": "FORD_MUSTANG_MACH_E_MK1"}

    with open(ROOT/"out"/"coeffs_v1.json", "w") as f:
        json.dump(out, f, indent=2)
    print("Saved coeffs to", ROOT/"out"/"coeffs_v1.json")
