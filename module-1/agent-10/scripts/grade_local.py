"""Local grader: run final-model/predict against sim-only inputs,
score against sim/ truth (yaw RMSE + distance-resampled CTE RMSE).
Also report V0 (passthrough) baseline for comparison.
"""
import glob, os, sys, numpy as np, pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-10"
sys.path.insert(0, os.path.join(ROOT, "final-model"))
from predict import predict  # noqa

SIM = os.path.join(ROOT, "data/sim/segments")
SIMONLY = os.path.join(ROOT, "data/sim-only/segments")

PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1", "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]


def _integrate(t, v, yaw):
    n = len(t); psi=np.zeros(n); x=np.zeros(n); y=np.zeros(n)
    for i in range(1, n):
        dt = t[i] - t[i-1]
        if dt <= 0 or not np.isfinite(dt):
            psi[i]=psi[i-1]; x[i]=x[i-1]; y[i]=y[i-1]; continue
        psi[i] = psi[i-1] + 0.5*(yaw[i]+yaw[i-1])*dt
        vxp=v[i-1]*np.cos(psi[i-1]); vyp=v[i-1]*np.sin(psi[i-1])
        vxc=v[i]*np.cos(psi[i]);     vyc=v[i]*np.sin(psi[i])
        x[i]=x[i-1]+0.5*(vxp+vxc)*dt
        y[i]=y[i-1]+0.5*(vyp+vyc)*dt
    return x,y


def resample_by_distance(x, y, ds=1.0):
    seg = np.hypot(np.diff(x), np.diff(y))
    s = np.concatenate(([0.0], np.cumsum(seg)))
    if s[-1] < 2*ds: return None, None, None
    s_new = np.arange(0, s[-1], ds)
    return s_new, np.interp(s_new, s, x), np.interp(s_new, s, y)


def cte_pair(xp, yp, xt, yt):
    sp, xpu, ypu = resample_by_distance(xp, yp, 1.0)
    st, xtu, ytu = resample_by_distance(xt, yt, 1.0)
    if sp is None or st is None: return None, 0
    n = min(len(sp), len(st))
    if n < 2: return None, 0
    e = np.hypot(xpu[:n]-xtu[:n], ypu[:n]-ytu[:n])
    return float(np.sqrt(np.mean(e*e))), int(n)


def truth_path(f): return f.replace("/data/sim-only/", "/data/sim/")


def main():
    for plat in PLATFORMS:
        files = sorted(glob.glob(os.path.join(SIMONLY, plat, "**", "sim.csv"), recursive=True))
        if not files:
            print(f"{plat}: no sim-only segs"); continue

        # accumulators
        yaw_v1 = [0.0, 0]; yaw_v0 = [0.0, 0]
        cte_v1 = [0.0, 0]; cte_v0 = [0.0, 0]
        skipped = 0
        for f in files:
            try:
                df_in = pd.read_csv(f)
            except Exception:
                skipped += 1; continue
            try:
                out = predict(df_in, plat)
            except Exception as e:
                print(f"predict failed on {f}: {e}"); skipped += 1; continue

            tp = truth_path(f)
            if not os.path.exists(tp):
                continue
            try:
                df_t = pd.read_csv(tp)
            except Exception:
                continue

            if "yaw_rate_meas_rads" in df_t.columns:
                y_t = df_t["yaw_rate_meas_rads"].values
                y_p = out["yaw_rate_pred_rads"].values
                y_0 = df_in["yaw_rate_pred_rads"].values
                n = min(len(y_t), len(y_p), len(y_0))
                m = np.isfinite(y_t[:n]) & np.isfinite(y_p[:n]) & np.isfinite(y_0[:n])
                e1 = y_p[:n][m] - y_t[:n][m]
                e0 = y_0[:n][m] - y_t[:n][m]
                yaw_v1[0] += np.sum(e1*e1); yaw_v1[1] += int(m.sum())
                yaw_v0[0] += np.sum(e0*e0); yaw_v0[1] += int(m.sum())

            if {"yaw_rate_meas_rads","v_mps","t_s"}.issubset(df_t.columns):
                t = df_t["t_s"].values
                v = df_t["v_mps"].values
                yaw_meas = df_t["yaw_rate_meas_rads"].values
                xt, yt = _integrate(t, v, yaw_meas)
                xp = out["x_m"].values; yp = out["y_m"].values
                n = min(len(xt), len(xp))
                r, m = cte_pair(xp[:n], yp[:n], xt[:n], yt[:n])
                if r is not None:
                    cte_v1[0] += r*r*m; cte_v1[1] += m
                yaw_v0_arr = df_in["yaw_rate_pred_rads"].values
                n2 = min(len(yaw_v0_arr), len(t))
                x0, y0 = _integrate(t[:n2], v[:n2], yaw_v0_arr[:n2])
                r0, m0 = cte_pair(x0[:n2], y0[:n2], xt[:n2], yt[:n2])
                if r0 is not None:
                    cte_v0[0] += r0*r0*m0; cte_v0[1] += m0

        print(f"\n{plat}  ({skipped} skipped)")
        if yaw_v1[1]:
            print(f"  yaw RMSE  V0={np.sqrt(yaw_v0[0]/yaw_v0[1]):.5f}  ->  V1={np.sqrt(yaw_v1[0]/yaw_v1[1]):.5f}  rad/s")
        if cte_v1[1]:
            print(f"  CTE RMSE  V0={np.sqrt(cte_v0[0]/cte_v0[1]):.3f}m  ->  V1={np.sqrt(cte_v1[0]/cte_v1[1]):.3f}m")


if __name__ == "__main__":
    main()
