import glob
import numpy as np
import pandas as pd

paths = sorted(glob.glob("/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-06/data/sim/segments/TESLA_MODEL_3/*/*/*/sim.csv"))[:50]
dfs = []
for p in paths:
    d = pd.read_csv(p)
    dfs.append(d)
D = pd.concat(dfs, ignore_index=True)
L = 2.875
ks_pred = D.v_mps / L * np.tan(D.delta_road_rad)
diff = D.psi_dot_rads - ks_pred
print("rows:", len(D))
print("psi_dot_rads stats:", D.psi_dot_rads.describe().to_string())
print("KS recompute - psi_dot_rads RMS:", float(np.sqrt(np.mean(diff**2))))
print("corr:", float(np.corrcoef(D.psi_dot_rads, ks_pred)[0,1]))
print("delta_state vs delta_road same?", float((D.delta_state_rad - D.delta_road_rad).abs().max()))
print("v_state vs v_mps same?", float((D.v_state_mps - D.v_mps).abs().max()))
