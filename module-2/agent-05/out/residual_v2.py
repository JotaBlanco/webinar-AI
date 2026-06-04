"""Run residual-structure on V2 to see what's left."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-05")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "residual-structure"))
sys.path.insert(0, str(ROOT / "out"))
from residual_structure import residual_structure, format_residual_structure_summary  # type: ignore
from fit_v2 import predict_factory_v2  # type: ignore


def main():
    import os
    os.chdir(ROOT)

    coeffs = json.loads((ROOT / "out" / "coeffs_v2.json").read_text())

    def predict_fn(sim_df, platform):
        cb = predict_factory_v2(platform, coeffs.get(platform, {}))
        yr = cb(sim_df)
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)

    res = residual_structure(predict_fn)
    print(format_residual_structure_summary(res))


if __name__ == "__main__":
    main()
