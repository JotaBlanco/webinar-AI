"""dst_regime smoke — same as dst_lin/dst_nl. Checks high/low gate behaviour."""

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


def _segment(*, high_speed: bool) -> pd.DataFrame:
    n, dt = 600, 0.01
    t = np.arange(n) * dt
    delta = 0.05 * np.sin(2 * np.pi * 0.5 * t)
    v = (15.0 + 0.05 * t) if high_speed else (2.5 + 0.005 * t)
    psi_v0 = v * np.tan(delta) / 3.0
    return pd.DataFrame({
        "t_s": t, "delta_wheel_deg": np.degrees(delta) * 16.0,
        "delta_road_rad": delta, "v_mps": v,
        "a_long_mps2": np.full(n, 0.05),
        "accel_pedal_pct": np.full(n, 30.0),
        "brake_pressed": np.zeros(n, dtype=int),
        "yaw_rate_pred_rads": psi_v0,
    })


def main() -> int:
    fails = 0
    for platform in PLATFORM_PRIORS:
        for mode in ("low_speed", "high_speed"):
            seg = _segment(high_speed=(mode == "high_speed"))
            try:
                out = predict(seg, platform)
            except Exception as e:
                print(f"  FAIL {platform}/{mode}: {type(e).__name__}: {e}")
                fails += 1
                continue
            arr = out["yaw_rate_pred_rads"].to_numpy()
            if not np.all(np.isfinite(arr)):
                print(f"  FAIL {platform}/{mode}: non-finite output"); fails += 1; continue
            if platform in PASSTHROUGH_PLATFORMS:
                if not np.allclose(arr, seg["yaw_rate_pred_rads"].to_numpy()):
                    print(f"  FAIL {platform}/{mode}: passthrough drift"); fails += 1; continue
            v0 = seg["yaw_rate_pred_rads"].to_numpy()
            rms = float(np.sqrt(np.mean((arr - v0) ** 2)))
            print(f"  ok   {platform}/{mode}: RMS(diff vs V0)={rms:.5f}")
    print(f"\n{2*len(PLATFORM_PRIORS) - fails}/{2*len(PLATFORM_PRIORS)} cases passed.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
