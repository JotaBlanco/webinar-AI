"""Plot one segment: measured vs predicted v, plus baseline."""
import json
import glob
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import sys
sys.path.insert(0, os.path.dirname(__file__))
from long_model import _features, fit_global, simulate_v, load_segments, PLATFORM

OUT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-08/out"

segs = load_segments(PLATFORM, limit=40)
beta = fit_global(segs[:20])

# Pick a longer / more dynamic segment from the eval set
best_idx = None
best_dyn = 0
for i, (_, df) in enumerate(segs[20:30]):
    dyn = df.v_mps.std()
    if dyn > best_dyn:
        best_dyn = dyn
        best_idx = i
path, df = segs[20 + best_idx]
v_meas = df.v_mps.values
t = df.t_s.values
T = df.di_torque_actual_nm.values
v_pred = simulate_v(df, beta)

# Cumulative drift contribution: integrate residual a
a_meas = df.a_long_mps2.values
a_pred = _features(df.v_mps.values, T) @ beta
res_a = a_meas - a_pred

fig, ax = plt.subplots(3, 1, figsize=(11, 8), sharex=True)
ax[0].plot(t, v_meas, label="measured v", color="black")
ax[0].plot(t, v_pred, label="closed-loop pred", color="C0")
ax[0].axhline(v_meas[0], color="C1", ls="--", label="hold-v0 baseline")
ax[0].set_ylabel("v [m/s]")
ax[0].legend(loc="best")
ax[0].set_title(f"Tesla M3 longitudinal closed-loop (driver-free) — seg {os.path.basename(os.path.dirname(path))}")

ax[1].plot(t, T, label="di_torque_actual [Nm] (input)", color="C2")
ax[1].axhline(0, color="grey", lw=0.5)
ax[1].set_ylabel("Motor torque [Nm]")
ax[1].legend()

ax[2].plot(t, a_meas, label="a IMU (truth)", color="black", lw=0.8)
ax[2].plot(t, a_pred, label="a model (open-loop)", color="C0", lw=0.8)
ax[2].set_ylabel("a [m/s²]")
ax[2].set_xlabel("t [s]")
ax[2].legend()
plt.tight_layout()
out_path = os.path.join(OUT, "long_model_example.png")
plt.savefig(out_path, dpi=110)
print(f"Wrote {out_path}")
print(f"Segment v_RMSE (closed-loop): {np.sqrt(np.mean((v_pred-v_meas)**2)):.3f}")
print(f"Segment v_RMSE (hold-v0)    : {np.sqrt(np.mean((v_meas[0]-v_meas)**2)):.3f}")
print(f"Segment a_RMSE (one-step)   : {np.sqrt(np.mean((a_pred-a_meas)**2)):.3f}")
