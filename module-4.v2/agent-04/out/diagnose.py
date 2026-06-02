"""Diagnose Mach-E CTE degradation."""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-04")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "out"))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "final-model"))
from v1_baseline import predict_v1
from score import find_segments, load_sim, ALLOW_COLS
from predict import predict as predict_final
from traj_metrics import cte_diagnostics_segment

plat = "FORD_MUSTANG_MACH_E_MK1"
paths = find_segments(plat, split="dev")[:40]
for p in paths[:10]:
    df = load_sim(p)
    if "yaw_rate_meas_rads" not in df.columns:
        continue
    sim_df = df[ALLOW_COLS].copy()
    v1 = predict_v1(sim_df, plat)["yaw_rate_pred_rads"].to_numpy()
    final = predict_final(sim_df, plat)["yaw_rate_pred_rads"].to_numpy()
    truth = df["yaw_rate_meas_rads"].to_numpy()
    t = df["t_s"].to_numpy(); v = df["v_mps"].to_numpy()
    d1 = cte_diagnostics_segment(t, v, truth, v1)
    d2 = cte_diagnostics_segment(t, v, truth, final)
    if d1["n_bins"] == 0:
        continue
    cte_v1 = np.sqrt(d1["sum_sq_m2"]/d1["n_bins"])
    cte_f = np.sqrt(d2["sum_sq_m2"]/d2["n_bins"])
    print(f"{Path(p).parent.name}: V1 cte={cte_v1:.2f} signed_mean={d1['sum_signed_m']/d1['n_bins']:.2f} | "
          f"FINAL cte={cte_f:.2f} signed_mean={d2['sum_signed_m']/d2['n_bins']:.2f} | "
          f"yaw_bias_v1={(v1-truth).mean():.5e} yaw_bias_f={(final-truth).mean():.5e}")
