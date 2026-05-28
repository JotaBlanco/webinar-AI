"""Sweep tau (steering-lag time-constant) and K_us scale to find optimum.

Provides an upper-bound sanity number too: per-segment OLS gain (the best
constant linear fit yaw_pred->yaw_meas could buy). Anything below that is
fixable; anything above is irreducible at this rung.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "data" / "sim" / "segments"
OUT = ROOT / "out"

L_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}
ST_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": dict(
        m=2336.0, l_f=1.3130, l_r=1.671, C_f=286_551.0, C_r=355_912.0, L=2.984,
    ),
    "FORD_F_150_LIGHTNING_MK1": dict(
        m=3084.0, l_f=1.628, l_r=2.072, C_f=378_307.0, C_r=469_878.0, L=3.70,
    ),
}


def k_us(p, scale=1.0):
    return scale * (p["m"] / p["L"]) * (p["l_r"] / p["C_f"] - p["l_f"] / p["C_r"])


def load(csv):
    rows = np.loadtxt(csv, delimiter=",", skiprows=1)
    if rows.ndim != 2 or rows.shape[0] < 100:
        return None
    return {
        "t": rows[:, 0],
        "delta": rows[:, 2],
        "v": rows[:, 3],
        "ay": rows[:, 5],
        "yaw": rows[:, 6],
    }


def estimate_bias(c):
    mask = (np.abs(c["yaw"]) < 0.02) & (np.abs(c["ay"]) < 0.3) & (c["v"] > 8.0)
    if mask.sum() < 50:
        return 0.0
    return float(np.median(c["delta"][mask]))


def lag(delta, dt, tau):
    if tau <= 0:
        return delta
    alpha = dt / (tau + dt)
    out = np.empty_like(delta)
    out[0] = delta[0]
    for k in range(1, len(delta)):
        out[k] = out[k - 1] + alpha * (delta[k] - out[k - 1])
    return out


def main():
    # Cache segments
    segs = []
    for plat_dir in sorted(SIM.iterdir()):
        if plat_dir.name not in L_BY_PLATFORM:
            continue
        for csv in sorted(plat_dir.rglob("sim.csv")):
            c = load(csv)
            if c is None:
                continue
            c["bias"] = estimate_bias(c)
            c["dt"] = float(np.median(np.diff(c["t"])))
            c["platform"] = plat_dir.name
            c["mask"] = c["v"] > 2.0
            if c["mask"].sum() < 50:
                continue
            segs.append(c)
    print(f"cached {len(segs)} segments")

    # Sweep tau in [0, 0.5] s, K_us scale in [0.5, 3.0]
    taus = [0.0, 0.02, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30, 0.40]
    scales = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]

    results = []
    for tau in taus:
        for scale in scales:
            sse_y = 0.0
            sse_a = 0.0
            n = 0
            for c in segs:
                p = ST_BY_PLATFORM[c["platform"]]
                Kus = k_us(p, scale)
                d_eff = lag(c["delta"] - c["bias"], c["dt"], tau)
                yp = (c["v"] * np.tan(d_eff)) / (p["L"] + Kus * c["v"] ** 2)
                ap = c["v"] * yp
                m = c["mask"]
                ey = (yp - c["yaw"])[m]
                ea = (ap - c["ay"])[m]
                sse_y += float(np.sum(ey * ey))
                sse_a += float(np.sum(ea * ea))
                n += int(m.sum())
            results.append({
                "tau": tau, "scale": scale,
                "rmse_yaw": float(np.sqrt(sse_y / n)),
                "rmse_ay": float(np.sqrt(sse_a / n)),
            })

    best_y = min(results, key=lambda r: r["rmse_yaw"])
    best_a = min(results, key=lambda r: r["rmse_ay"])
    print("best yaw:", best_y)
    print("best ay :", best_a)

    # Per-platform best
    for plat in L_BY_PLATFORM:
        plat_segs = [c for c in segs if c["platform"] == plat]
        per_plat = []
        for tau in taus:
            for scale in scales:
                sse_y = 0.0
                n = 0
                for c in plat_segs:
                    p = ST_BY_PLATFORM[plat]
                    Kus = k_us(p, scale)
                    d_eff = lag(c["delta"] - c["bias"], c["dt"], tau)
                    yp = (c["v"] * np.tan(d_eff)) / (p["L"] + Kus * c["v"] ** 2)
                    m = c["mask"]
                    ey = (yp - c["yaw"])[m]
                    sse_y += float(np.sum(ey * ey))
                    n += int(m.sum())
                per_plat.append({"tau": tau, "scale": scale, "rmse_yaw": float(np.sqrt(sse_y / n))})
        b = min(per_plat, key=lambda r: r["rmse_yaw"])
        print(f"  best yaw [{plat}]: tau={b['tau']} scale={b['scale']} rmse={b['rmse_yaw']:.6f}")

    (OUT / "tune.json").write_text(json.dumps({"grid": results, "best_yaw": best_y, "best_ay": best_a}, indent=2))


if __name__ == "__main__":
    main()
