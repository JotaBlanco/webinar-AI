"""Plot v_pred vs v_meas for one held-out segment."""
import sys, json
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-06/tools")
from fit_longitudinal_v2 import (
    load_segments, load_one, fit_pieces,
    integrate_closed_loop, integrate_closed_loop_windowed, integrate_imu_baseline
)

paths = load_segments()
rng = np.random.default_rng(42); rng.shuffle(paths)
n_train = int(0.7 * len(paths))
train, test = paths[:n_train], paths[n_train:]
model = fit_pieces(train)

# Pick a few representative test segments
sel = test[:3]
fig, axes = plt.subplots(len(sel), 1, figsize=(10, 3*len(sel)), sharex=False)
if len(sel) == 1: axes = [axes]
for ax, p in zip(axes, sel):
    df = load_one(p)
    vm = df["v_mps"].values
    t  = df["t_s"].values
    vp = integrate_closed_loop(df, model)
    vp10 = integrate_closed_loop_windowed(df, model, 10.0)
    vi = integrate_imu_baseline(df)
    ax.plot(t, vm, "k-", lw=1.5, label="v_meas (truth)")
    ax.plot(t, vp, "r-", lw=1.0, label="fitted model (full-segment closed-loop)")
    ax.plot(t, vp10, "b-", lw=1.0, label="fitted model (10s windowed)")
    ax.plot(t, vi, "g--", lw=0.8, label="IMU integrated (baseline)")
    ax.set_ylabel("v [m/s]")
    ax.legend(loc="best", fontsize=7)
    ax.set_title(p.split("/")[-3]+"/"+p.split("/")[-2])
axes[-1].set_xlabel("t [s]")
plt.tight_layout()
plt.savefig("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-06/out/v_trace_examples.png", dpi=120)
print("saved")
