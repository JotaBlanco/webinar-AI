"""Plot one closed-loop segment: v_pred vs v_meas, plus the a channels."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import sys

sys.path.insert(0, "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-02/tools")
from load_segments import find_csvs, load_segment
from long_model import fit, predict_a, closed_loop_segment

OUT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-02/out")
OUT.mkdir(exist_ok=True)

# Re-fit on a random 80% training subset for reproducibility
csvs = find_csvs()
rng = np.random.default_rng(42)
idx = np.arange(len(csvs)); rng.shuffle(idx)
n_train = int(0.8 * len(idx))
train_csvs = [csvs[i] for i in idx[:n_train]]
test_csvs  = [csvs[i] for i in idx[n_train:]]

df_train = pd.concat([load_segment(c) for c in train_csvs[:200]], ignore_index=True)  # cap for speed
df_train = df_train.dropna(subset=["v_mps", "a_long_mps2", "accel_pedal_pct", "brake_pressed"])
coef = fit(df_train)
print("coef:", coef)

# pick a few test segments with variety
for i, c in enumerate(test_csvs[:6]):
    seg = load_segment(c).dropna(subset=["v_mps", "a_long_mps2", "accel_pedal_pct", "brake_pressed"]).reset_index(drop=True)
    if len(seg) < 100: continue
    seg = closed_loop_segment(seg, coef)
    seg["a_pred_ol"] = predict_a(seg, coef, v_col="v_mps")

    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    t = seg["t_s"]
    axes[0].plot(t, seg["v_mps"], "k-", label="v_meas (truth)")
    axes[0].plot(t, seg["v_pred_cl"], "r-", label="v_pred (closed loop, our model)")
    axes[0].set_ylabel("v [m/s]"); axes[0].legend(); axes[0].grid(alpha=0.3)

    axes[1].plot(t, seg["a_long_mps2"], "k-", alpha=0.7, label="a_meas (IMU)")
    axes[1].plot(t, seg["a_pred_ol"],   "b-", alpha=0.7, label="a_pred (open loop)")
    axes[1].plot(t, seg["a_pred_cl"],   "r-", alpha=0.5, label="a_pred (closed loop)")
    axes[1].set_ylabel("a [m/s^2]"); axes[1].legend(); axes[1].grid(alpha=0.3)

    axes[2].plot(t, seg["accel_pedal_pct"], "g-", label="accel %")
    axes[2].plot(t, seg["brake_pressed"]*50, "m-", label="brake*50")
    axes[2].set_xlabel("t [s]"); axes[2].set_ylabel("driver inputs"); axes[2].legend(); axes[2].grid(alpha=0.3)

    rmse = float(np.sqrt(np.mean((seg["v_pred_cl"] - seg["v_mps"])**2)))
    fig.suptitle(f"{c.parts[-5]}/{c.parts[-3]}/{c.parts[-2]}  v_RMSE={rmse:.2f} m/s")
    fig.tight_layout()
    fig.savefig(OUT / f"closed_loop_seg_{i}.png", dpi=110)
    plt.close(fig)
    print(f"wrote closed_loop_seg_{i}.png  v_RMSE={rmse:.2f} m/s")

print("done")
