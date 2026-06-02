"""dst_nl/smoke.py — synthetic-data smoke test for dst_nl.predict()."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_MODEL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_MODEL_DIR.parent))
sys.path.insert(0, str(_MODEL_DIR))

from _common import PASSTHROUGH_PLATFORMS, PLATFORM_PRIORS  # noqa: E402
from predict import predict  # noqa: E402


def _synthetic_segment(n: int = 600, dt: float = 0.01, *, high_alpha: bool = False) -> pd.DataFrame:
    t = np.arange(n) * dt
    # high_alpha mode hits a saturation regime (large delta + high v).
    amp = 0.15 if high_alpha else 0.05
    delta = amp * np.sin(2 * np.pi * 0.5 * t)
    v = 12.0 + 0.1 * t if high_alpha else 5.0 + 0.05 * t
    a_long = np.full(n, 0.05)
    psi_dot_v0 = v * np.tan(delta) / 3.0
    return pd.DataFrame({
        "t_s": t,
        "delta_wheel_deg": np.degrees(delta) * 16.0,
        "delta_road_rad": delta,
        "v_mps": v,
        "a_long_mps2": a_long,
        "accel_pedal_pct": np.full(n, 30.0),
        "brake_pressed": np.zeros(n, dtype=int),
        "yaw_rate_pred_rads": psi_dot_v0,
    })


def main() -> int:
    fails = 0
    for platform in PLATFORM_PRIORS:
        for mode in ("low_alpha", "high_alpha"):
            seg = _synthetic_segment(high_alpha=(mode == "high_alpha"))
            try:
                out = predict(seg, platform)
            except Exception as e:
                print(f"  FAIL {platform}/{mode}: predict raised {type(e).__name__}: {e}")
                fails += 1
                continue
            arr = out["yaw_rate_pred_rads"].to_numpy()
            if not np.all(np.isfinite(arr)):
                print(f"  FAIL {platform}/{mode}: non-finite output")
                fails += 1
                continue
            if platform in PASSTHROUGH_PLATFORMS:
                if not np.allclose(arr, seg["yaw_rate_pred_rads"].to_numpy()):
                    print(f"  FAIL {platform}/{mode}: passthrough drift")
                    fails += 1
                    continue
            v0_rms = float(np.sqrt(np.mean(seg["yaw_rate_pred_rads"]**2))) + 1e-9
            rms = float(np.sqrt(np.mean((arr - seg["yaw_rate_pred_rads"].to_numpy())**2)))
            print(f"  ok   {platform}/{mode}: RMS(diff vs V0)={rms:.5f}, "
                  f"ratio={rms/v0_rms:.2f}")
    print(f"\n{2*len(PLATFORM_PRIORS) - fails}/{2*len(PLATFORM_PRIORS)} cases passed.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
