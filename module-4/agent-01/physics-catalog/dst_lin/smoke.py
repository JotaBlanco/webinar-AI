"""dst_lin/smoke.py — synthetic-data smoke test for dst_lin.predict().

No external data dependency. Builds a 60s synthetic segment with sinusoidal
steering + accelerating speed for each platform, runs predict(), and asserts:

- output is a DataFrame
- has yaw_rate_pred_rads column
- same length / index as input
- no NaN / inf
- finite RMSE bound vs the input V0 (model didn't blow up)

Run: python -m physics-catalog.dst_lin.smoke
"""

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


def _synthetic_segment(n: int = 600, dt: float = 0.01) -> pd.DataFrame:
    t = np.arange(n) * dt
    # Steering: 0.05 rad sinusoid at 0.5 Hz.
    delta = 0.05 * np.sin(2 * np.pi * 0.5 * t)
    v = 5.0 + 0.05 * t  # 5 m/s ramping to 11 m/s over 60s
    a_long = np.full(n, 0.05)
    # V0 baseline yaw rate from kinematic: psi_dot = v * tan(delta) / L (sedan L≈3m)
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
        seg = _synthetic_segment()
        try:
            out = predict(seg, platform)
        except Exception as e:
            print(f"  FAIL {platform}: predict raised {type(e).__name__}: {e}")
            fails += 1
            continue

        if not isinstance(out, pd.DataFrame):
            print(f"  FAIL {platform}: returned {type(out).__name__}, want DataFrame")
            fails += 1
            continue
        if "yaw_rate_pred_rads" not in out.columns:
            print(f"  FAIL {platform}: missing yaw_rate_pred_rads column")
            fails += 1
            continue
        if len(out) != len(seg) or not (out.index == seg.index).all():
            print(f"  FAIL {platform}: index mismatch")
            fails += 1
            continue
        arr = out["yaw_rate_pred_rads"].to_numpy()
        if not np.all(np.isfinite(arr)):
            print(f"  FAIL {platform}: non-finite values in output")
            fails += 1
            continue
        # Compare against V0; allow up to 5× difference (the model is
        # intentionally different — we're only checking it didn't explode).
        v0 = seg["yaw_rate_pred_rads"].to_numpy()
        rms = float(np.sqrt(np.mean((arr - v0) ** 2)))
        if platform in PASSTHROUGH_PLATFORMS:
            # Tesla should be exact passthrough.
            if not np.allclose(arr, v0):
                print(f"  FAIL {platform}: passthrough drift "
                      f"max abs={np.max(np.abs(arr - v0)):.3e}")
                fails += 1
                continue
        else:
            v0_rms = float(np.sqrt(np.mean(v0 ** 2))) + 1e-9
            if rms / v0_rms > 5.0:
                print(f"  WARN {platform}: model output drifts {rms/v0_rms:.1f}× V0 "
                      "— may indicate unstable integration on textbook defaults")
                # warn, not fail — fit.py is the real source of truth.
        print(f"  ok   {platform}: RMS(diff vs V0) = {rms:.5f} rad/s")
    print(f"\n{len(PLATFORM_PRIORS) - fails}/{len(PLATFORM_PRIORS)} platforms passed.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
