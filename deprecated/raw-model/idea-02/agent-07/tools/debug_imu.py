import glob, numpy as np, pandas as pd
BASE = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-07/data/sim/segments"
ford = sorted(glob.glob(f"{BASE}/FORD_*/**/sim.csv", recursive=True))
for f in ford[:5]:
    d = pd.read_csv(f)
    t = d["t_s"].values
    v = d["v_mps"].values
    a = d["a_long_mps2"].values
    dv_dt = np.gradient(v, t)
    bias = np.mean(a - dv_dt)
    print(f"{f.split('/')[-3]}: bias(a-dv/dt)={bias:+.4f}  a_mean={a.mean():+.3f}  dv_dt_mean={dv_dt.mean():+.3f}  v0={v[0]:.2f} vN={v[-1]:.2f}")
    # closed-loop integration of raw a
    vi = np.empty_like(v); vi[0] = v[0]
    for k in range(len(v)-1):
        vi[k+1] = vi[k] + a[k]*(t[k+1]-t[k])
    print(f"  raw-IMU drift at end: {vi[-1]-v[-1]:+.2f} m/s")
    vi2 = np.empty_like(v); vi2[0] = v[0]
    for k in range(len(v)-1):
        vi2[k+1] = vi2[k] + (a[k]-bias)*(t[k+1]-t[k])
    print(f"  bias-corrected drift at end: {vi2[-1]-v[-1]:+.2f} m/s")
