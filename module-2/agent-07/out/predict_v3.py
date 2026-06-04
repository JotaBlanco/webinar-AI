"""V3 candidate predict, scored against V2 before promotion."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-07")
COEFFS = json.loads((ROOT / "out" / "coeffs_v3.json").read_text())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)
    c = COEFFS.get(platform)
    if c is None or c.get("passthrough"):
        out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].to_numpy(float)
        return out
    t = sim_df["t_s"].to_numpy(float)
    d = sim_df["delta_road_rad"].to_numpy(float)
    v = sim_df["v_mps"].to_numpy(float)
    dd = np.gradient(d, t) if len(t) > 1 else np.zeros_like(d)
    gain=c["gain"]; K_us=c["K_us"]; tau=c["tau"]; tau2=c["tau2"]
    d_off=c["delta_off"]; cub=c["cub"]
    tau_eff = tau + tau2 * (v*v) / 100.0
    delta_eff = (d - d_off) + tau_eff * dd - cub * (d ** 3)
    out["yaw_rate_pred_rads"] = gain * v * delta_eff / (1.0 + K_us * v * v)
    return out


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "skills" / "score-model"))
    sys.path.insert(0, str(ROOT / "_shared"))
    from score import score, format_summary
    paths = sorted(p for p in (ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv") if p.is_file())
    res = score(predict, segment_paths=paths)
    print(format_summary(res))
