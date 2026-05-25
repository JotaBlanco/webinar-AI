"""Render report.png — predicted vs measured yaw rate for a transient-heavy
segment, one trace per variant.
"""

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

MODULE = Path(__file__).resolve().parents[1]
NPZ = MODULE / "tools" / "preds.npz"
OUT = MODULE / "report.png"

# Picked because it has the largest transient-sample count (469 / 2898).
SEG = "FORD__0b2c0b_34"

VARIANTS = [
    ("v0_ks_stock",      "tab:gray",   "-",  1.2),
    ("v1_ks_Leff",       "tab:olive",  "-",  1.2),
    ("v2_st_canonical",  "tab:orange", "-",  1.2),
    ("v3_st_calibrated", "tab:red",    "-",  1.4),
    ("v4_st_residual",   "tab:blue",   "--", 1.0),
]


def main() -> None:
    d = np.load(NPZ, allow_pickle=False)
    t = d[f"t__{SEG}"]
    meas = d[f"meas__{SEG}"]
    regime = d[f"regime__{SEG}"].astype(str)

    # Pick a 20 s window with the highest transient density.
    win = 20.0   # s
    dt = float(np.median(np.diff(t)))
    w = int(win / dt)
    trn_flag = (regime == "transient").astype(int)
    csum = np.cumsum(np.r_[0, trn_flag])
    counts = csum[w:] - csum[:-w]
    i0 = int(np.argmax(counts))
    i1 = i0 + w
    t_win = t[i0:i1]
    meas_win = meas[i0:i1]
    reg_win = regime[i0:i1]

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(12, 7), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    # Shade transient regions on the top axis.
    transient_idx = np.where(reg_win == "transient")[0]
    if transient_idx.size:
        # group consecutive indices
        breaks = np.where(np.diff(transient_idx) > 1)[0]
        groups = np.split(transient_idx, breaks + 1)
        for g in groups:
            ax_top.axvspan(t_win[g[0]], t_win[g[-1]],
                           color="tab:red", alpha=0.05, linewidth=0)

    ax_top.plot(t_win, np.degrees(meas_win), color="black",
                linewidth=1.8, label="measured (bias-corrected)", zorder=10)
    for name, color, ls, lw in VARIANTS:
        pred = d[f"{name}__{SEG}"][i0:i1]
        ax_top.plot(t_win, np.degrees(pred), color=color, linestyle=ls,
                    linewidth=lw, label=name, alpha=0.95)

    ax_top.set_ylabel("yaw rate  [deg/s]")
    ax_top.set_title(
        f"Predicted vs measured yaw rate — segment {SEG}  "
        f"(transient-heavy 20 s window; pink = transient samples)"
    )
    ax_top.legend(loc="upper right", ncols=2, fontsize=9, framealpha=0.95)
    ax_top.grid(alpha=0.3)

    # Bottom: residual of v0 stock and v3 calibrated, to make the closure
    # visually obvious.
    resid_v0 = np.degrees(meas_win - d[f"v0_ks_stock__{SEG}"][i0:i1])
    resid_v3 = np.degrees(meas_win - d[f"v3_st_calibrated__{SEG}"][i0:i1])
    ax_bot.axhline(0, color="black", linewidth=0.5)
    ax_bot.plot(t_win, resid_v0, color="tab:gray", linewidth=1.0,
                label="resid v0 (KS stock)")
    ax_bot.plot(t_win, resid_v3, color="tab:red", linewidth=1.2,
                label="resid v3 (ST calibrated)")
    ax_bot.set_ylabel("residual  [deg/s]")
    ax_bot.set_xlabel("time within segment  [s]")
    ax_bot.legend(loc="upper right", fontsize=9, framealpha=0.95)
    ax_bot.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(OUT, dpi=140)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
