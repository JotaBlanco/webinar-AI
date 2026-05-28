"""Quick sign-convention diagnostic."""
import numpy as np
import pandas as pd
from pathlib import Path

SIM_ROOT = Path(__file__).resolve().parents[1] / "data" / "sim" / "segments" / "TESLA_MODEL_3"
csvs = sorted(SIM_ROOT.glob("*/*/*/sim.csv"))[:5]

L = 2.875

for p in csvs:
    df = pd.read_csv(p)
    if not {"wheel_RL_kph","wheel_RR_kph","v_mps","delta_road_rad","psi_dot_rads"}.issubset(df.columns):
        continue
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    v_rl = df["wheel_RL_kph"].to_numpy()/3.6
    v_rr = df["wheel_RR_kph"].to_numpy()/3.6
    ks_psidot = df["psi_dot_rads"].to_numpy()
    # Truth candidates:
    truth_rr_minus_rl = (v_rr - v_rl) / 1.580
    truth_rl_minus_rr = (v_rl - v_rr) / 1.580
    mask = v >= 5.0
    # Correlation with KS prediction (which uses tan(delta)*v/L, openpilot sign convention)
    c1 = np.corrcoef(ks_psidot[mask], truth_rr_minus_rl[mask])[0,1] if mask.sum() else float('nan')
    c2 = np.corrcoef(ks_psidot[mask], truth_rl_minus_rr[mask])[0,1] if mask.sum() else float('nan')
    cd = np.corrcoef(ks_psidot[mask], delta[mask])[0,1] if mask.sum() else float('nan')
    print(f"{p.parent.parent.name}/{p.parent.name}")
    print(f"  corr(KS, RR-RL) = {c1:+.3f}   corr(KS, RL-RR) = {c2:+.3f}   corr(KS, delta)={cd:+.3f}")
    # Magnitude ratio (median ratio of |truth|/|KS|) over significant samples
    big = mask & (np.abs(ks_psidot) > np.deg2rad(2))
    if big.sum():
        ratio = np.median(truth_rr_minus_rl[big] / ks_psidot[big])
        print(f"  median(truth/KS)={ratio:+.3f}   (n={big.sum()})")
