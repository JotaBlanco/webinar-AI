"""Plot a couple of example v_meas vs v_pred traces (closed-loop) for visual sanity."""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent))
from build_long_model import (
    fit_long_model, integrate_closed_loop, list_sim_csvs, load_csv, split, PLATFORMS,
)

OUT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-09/out")


def main():
    fig, axes = plt.subplots(3, 2, figsize=(11, 9), constrained_layout=True)
    for row, platform in enumerate(PLATFORMS):
        csvs = list_sim_csvs(platform)
        if len(csvs) < 4:
            continue
        train, test = split(csvs, max_total=80)
        theta = fit_long_model(train)
        # plot 2 test segments
        for col in range(2):
            if col >= len(test):
                break
            d = load_csv(test[col])
            v = d["v_mps"]; a = d["a_long_mps2"]
            keep = (np.isfinite(v) & np.isfinite(a)
                    & (v >= 0) & (v < 80) & (np.abs(a) < 12.0))
            d = {k: (vv[keep] if hasattr(vv, "shape") and vv.ndim == 1 and vv.shape[0] == keep.shape[0] else vv) for k, vv in d.items()}
            if d["t_s"].size < 50:
                continue
            v_pred = integrate_closed_loop(theta, d)
            t = d["t_s"]
            v_meas = d["v_mps"]
            ax = axes[row, col]
            ax.plot(t, v_meas, "k-", lw=1.4, label="v_meas")
            ax.plot(t, v_pred, "C1-", lw=1.2, label="v_pred (closed-loop)")
            ax.plot(t, np.full_like(t, v_meas[0]), "C7--", lw=0.8, label="hold v(0)")
            ax.set_title(f"{platform}  {test[col].parent.parent.name[:8]}/{test[col].parent.name}", fontsize=9)
            ax.set_xlabel("t [s]"); ax.set_ylabel("v [m/s]")
            ax.legend(fontsize=7)
            ax.grid(alpha=0.3)
    out = OUT / "long_model_traces.png"
    fig.savefig(out, dpi=120)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
