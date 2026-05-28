"""Evaluate closed-loop v prediction at multiple horizons.

Slides a window across each test segment and re-seeds v_pred to v_meas at the
start of each window.  Reports v_RMSE at the END of the window — that's the
'how far has the model drifted after H seconds' number.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-02/tools")
from load_segments import find_csvs, load_segment
from long_model import fit, closed_loop_segment


def eval_horizon(seg, coef, horizon_s, stride_s=1.0):
    """Return per-window terminal-v RMSE."""
    t = seg["t_s"].values
    dt = float(np.median(np.diff(t)))
    H = max(int(horizon_s / dt), 2)
    S = max(int(stride_s / dt), 1)
    errs = []
    for k0 in range(0, len(seg) - H, S):
        sub = seg.iloc[k0:k0+H].reset_index(drop=True)
        sub_cl = closed_loop_segment(sub, coef)
        # terminal error
        e = sub_cl["v_pred_cl"].iloc[-1] - sub_cl["v_mps"].iloc[-1]
        errs.append(float(e))
    return np.array(errs)


def main():
    csvs = find_csvs()
    rng = np.random.default_rng(42)
    idx = np.arange(len(csvs)); rng.shuffle(idx)
    n_train = int(0.8 * len(idx))
    train_csvs = [csvs[i] for i in idx[:n_train]]
    test_csvs  = [csvs[i] for i in idx[n_train:]]

    df_train = pd.concat([load_segment(c) for c in train_csvs], ignore_index=True)
    df_train = df_train.dropna(subset=["v_mps", "a_long_mps2", "accel_pedal_pct", "brake_pressed"])
    coef = fit(df_train)

    horizons = [1.0, 2.0, 5.0, 10.0, 20.0]
    bucket = {h: [] for h in horizons}
    for c in test_csvs[:60]:
        seg = load_segment(c).dropna(subset=["v_mps", "a_long_mps2", "accel_pedal_pct", "brake_pressed"]).reset_index(drop=True)
        if len(seg) < 100: continue
        for h in horizons:
            if seg["t_s"].iloc[-1] < h + 1: continue
            errs = eval_horizon(seg, coef, h)
            if len(errs):
                bucket[h].extend(errs.tolist())

    print(f"\nTerminal v_pred error vs horizon (60 test segments, sliding 1 s stride):")
    print(f"{'horizon':>10} {'N':>8} {'mean|err|':>12} {'RMSE':>8} {'p50|err|':>10} {'p90|err|':>10}")
    for h in horizons:
        e = np.array(bucket[h])
        if len(e) == 0:
            print(f"{h:>10.1f} {'-':>8}")
            continue
        ae = np.abs(e)
        print(f"{h:>10.1f} {len(e):>8d} {ae.mean():>12.3f} {np.sqrt((e**2).mean()):>8.3f} "
              f"{np.median(ae):>10.3f} {np.percentile(ae,90):>10.3f}")


if __name__ == "__main__":
    main()
