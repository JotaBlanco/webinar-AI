"""dst_relax smoke — synthetic data, all platforms."""

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


def _segment(n: int = 600, dt: float = 0.01) -> pd.DataFrame:
    t = np.arange(n) * dt
    # Step in steering — best regime to surface tyre-relaxation lag.
    delta = np.where(t > 1.0, 0.05, 0.0)
    v = 12.0 + 0.05 * t
    psi_v0 = v * np.tan(delta) / 3.0
    return pd.DataFrame({
        "t_s": t, "delta_wheel_deg": np.degrees(delta) * 16.0,
        "delta_road_rad": delta, "v_mps": v, "a_long_mps2": np.full(n, 0.05),
        "accel_pedal_pct": np.full(n, 30.0), "brake_pressed": np.zeros(n, dtype=int),
        "yaw_rate_pred_rads": psi_v0,
    })


def main() -> int:
    fails = 0
    for platform in PLATFORM_PRIORS:
        seg = _segment()
        try:
            out = predict(seg, platform)
        except Exception as e:
            print(f"  FAIL {platform}: {type(e).__name__}: {e}"); fails += 1; continue
        arr = out["yaw_rate_pred_rads"].to_numpy()
        if not np.all(np.isfinite(arr)):
            print(f"  FAIL {platform}: non-finite output"); fails += 1; continue
        if platform in PASSTHROUGH_PLATFORMS:
            if not np.allclose(arr, seg["yaw_rate_pred_rads"].to_numpy()):
                print(f"  FAIL {platform}: passthrough drift"); fails += 1; continue
        v0 = seg["yaw_rate_pred_rads"].to_numpy()
        rms = float(np.sqrt(np.mean((arr - v0) ** 2)))
        print(f"  ok   {platform}: RMS(diff vs V0)={rms:.5f}")
    print(f"\n{len(PLATFORM_PRIORS) - fails}/{len(PLATFORM_PRIORS)} platforms passed.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
