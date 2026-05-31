"""Try adding a first-order lag to V3 to capture tire/yaw transient."""
import sys
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent

DATA_ROOT = HERE / "data" / "sim" / "segments"
PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]
L_BY = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}


def list_segments(platform):
    return sorted((DATA_ROOT / platform).glob("**/sim.csv"))


def split_train_dev(paths, frac=0.7, seed=42):
    rng = np.random.default_rng(seed)
    idx = np.arange(len(paths))
    rng.shuffle(idx)
    cut = int(len(paths) * frac)
    return [paths[i] for i in idx[:cut]], [paths[i] for i in idx[cut:]]


def predict_v3_seg(delta, v, L, K_us, a_scale, b_off):
    return v * (a_scale * delta + b_off) / (L + K_us * v * v)


def predict_v5_seg(delta, v, t, L, K_us, a_scale, b_off, tau):
    """V5 = V3 with a first-order lag on the steady-state output."""
    yr_ss = predict_v3_seg(delta, v, L, K_us, a_scale, b_off)
    if tau <= 1e-4:
        return yr_ss
    y = np.empty_like(yr_ss)
    y[0] = yr_ss[0]
    for k in range(1, len(yr_ss)):
        dt = t[k] - t[k - 1]
        alpha = dt / (tau + dt)
        y[k] = y[k - 1] + alpha * (yr_ss[k] - y[k - 1])
    return y


def seg_loss_v5(segs, params, L0, v_min=2.0):
    K_us, a, b, tau = params
    sse = 0.0
    n = 0
    for (delta, v, yr_meas, t) in segs:
        m = v > v_min
        if m.sum() < 2: continue
        pred = predict_v5_seg(delta, v, t, L0, K_us, a, b, tau)
        r = pred[m] - yr_meas[m]
        sse += float(np.sum(r * r))
        n += int(m.sum())
    return sse / max(n, 1)


def load_segs(paths):
    out = []
    for p in paths:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        out.append((
            df["delta_road_rad"].to_numpy(),
            df["v_mps"].to_numpy(),
            df["yaw_rate_meas_rads"].to_numpy(),
            df["t_s"].to_numpy(),
        ))
    return out


def fit_v5(segs_train, L0, init):
    def loss(params):
        if params[3] < 0: return 1e9
        return seg_loss_v5(segs_train, params, L0)
    res = minimize(loss, init, method="Nelder-Mead",
                   options={"xatol": 1e-6, "fatol": 1e-10, "maxiter": 3000})
    return res.x, res.fun


def main():
    with open(HERE / "_fit_results.json") as f:
        prior = json.load(f)
    out_coeffs = {}
    for platform in PLATFORMS:
        paths = list_segments(platform)
        train, dev = split_train_dev(paths)
        L0 = L_BY[platform]
        c3 = prior["coeffs"][platform]["v3"]
        segs_train = load_segs(train)
        segs_dev = load_segs(dev)
        print(f"\n=== {platform} (L={L0}) ===")
        # Baseline V3 evaluated per-segment (no lag) on dev
        v3_loss_dev = seg_loss_v5(segs_dev, [c3["K_us"], c3["a_scale"], c3["b_off"], 0.0], L0)
        print(f"  V3 dev RMSE: {v3_loss_dev**0.5:.6f}")

        # V5 fit
        params, tr_loss = fit_v5(segs_train, L0,
                                 [c3["K_us"], c3["a_scale"], c3["b_off"], 0.05])
        v5_loss_dev = seg_loss_v5(segs_dev, params, L0)
        print(f"  V5 train RMSE: {tr_loss**0.5:.6f}")
        print(f"  V5 dev   RMSE: {v5_loss_dev**0.5:.6f}  params(K_us,a,b,tau)={params}")

        out_coeffs[platform] = dict(
            L=L0,
            K_us=float(params[0]),
            a_scale=float(params[1]),
            b_off=float(params[2]),
            tau=float(max(params[3], 0.0)),
        )

    with open(HERE / "_fit_v5.json", "w") as f:
        json.dump(out_coeffs, f, indent=2)
    print("\nWrote _fit_v5.json")


if __name__ == "__main__":
    main()
