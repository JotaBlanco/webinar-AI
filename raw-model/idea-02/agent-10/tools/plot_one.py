"""Plot predicted vs measured v for one representative segment per platform."""
import sys, glob
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from long_model import (collect_platform, fit_model, closed_loop_rmse,
                         baseline_constant, baseline_constant_rmse, OUT)

for plat in ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1", "TESLA_MODEL_3"):
    segs = collect_platform(plat, 80)
    if not segs:
        continue
    train = [s for s in segs if hash(s["name"]) % 5 < 3]
    test  = [s for s in segs if hash(s["name"]) % 5 >= 3]
    if not train or not test:
        continue
    coef = fit_model(train)
    a_c = baseline_constant(train)
    s = test[len(test)//2]   # pick a middle one
    r = closed_loop_rmse(s, coef)
    b = baseline_constant_rmse(s, a_c)

    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    axes[0].plot(s["t"], s["v"], "k", label="measured v", lw=2)
    axes[0].plot(s["t"], r["v_pred"], "C0", label=f"model v (RMSE {r['rmse']:.2f})", lw=1.2)
    axes[0].plot(s["t"], b["v_pred"], "C3--", label=f"baseline const-a (RMSE {b['rmse']:.2f})", lw=1.0)
    axes[0].set_ylabel("v [m/s]")
    axes[0].legend(); axes[0].grid(True, alpha=0.3)
    axes[0].set_title(f"{plat}  segment: {s['name']}")

    axes[1].plot(s["t"], s["a"], "k", label="measured a_long", lw=1.2, alpha=0.7)
    axes[1].plot(s["t"], r["a_pred"], "C0", label="predicted a_long (closed-loop)", lw=1.0)
    axes[1].set_xlabel("t [s]"); axes[1].set_ylabel("a [m/s²]")
    axes[1].legend(); axes[1].grid(True, alpha=0.3)

    out_png = OUT / f"long_model_{plat}.png"
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    plt.close(fig)
    print(f"wrote {out_png}")
