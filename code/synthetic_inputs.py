"""Synthetic driver inputs for the KS demo.

A 60-second highway-ish drive a Model 3 owner would recognise:

  - 0-8 s    : cruise straight at 25 m/s (90 km/h)
  - 8-12 s   : single lane change to the left (low-amplitude sinusoid in delta)
  - 12-22 s  : cruise straight
  - 22-30 s  : brake from 25 to 20 m/s entering an off-ramp (a ≈ -0.7 m/s²)
  - 26-46 s  : sweeping right-hand off-ramp arc — modest delta, ~90° of heading
  - 28-32 s  : brief tightening "spirited" mid-corner peak that just crosses the
               ±5 m/s² ST-linear-tyre honest band (pedagogically deliberate —
               the audience sees the model leave its honest regime live)
  - 46-60 s  : cruise straight at 20 m/s

Outputs `(t, delta(t), a(t))` plus a `delta_meas` array of the same trace
(since this IS the measured steering — there's no separate sensor in synthetic
mode).
"""

import numpy as np

from ks_model import KSDriverInputs


def make_demo_inputs(
    duration_s: float = 60.0,
    sample_rate_hz: float = 100.0,
) -> KSDriverInputs:
    dt = 1.0 / sample_rate_hz
    N = int(duration_s * sample_rate_hz)
    t = np.arange(N) * dt

    # ---- Steering (road-wheel angle, rad) ------------------------------------
    delta = np.zeros(N)

    # Lane change 8-12 s: full sinusoid, peak ±0.005 rad (~0.3° road-wheel,
    # ≈3° at the steering wheel after i_s ~= 11). Realistic highway lane change.
    lc_mask = (t >= 8.0) & (t < 12.0)
    delta[lc_mask] = 0.005 * np.sin(2 * np.pi * (t[lc_mask] - 8.0) / 4.0)

    # Sweeping off-ramp 26-46 s: smooth cosine ramp up, hold, ramp down.
    # Base level 0.015 rad (~0.86° road wheel). At v ≈ 20 m/s this gives
    # yaw rate ~ 0.10 rad/s = 6°/s, lateral G ~ 2.1 m/s² — typical highway
    # off-ramp.
    def cosine_pulse(t_arr, t0, t1, t2, t3, peak):
        # ramp up [t0,t1], hold [t1,t2], ramp down [t2,t3]
        out = np.zeros_like(t_arr)
        m1 = (t_arr >= t0) & (t_arr < t1)
        m2 = (t_arr >= t1) & (t_arr < t2)
        m3 = (t_arr >= t2) & (t_arr < t3)
        out[m1] = peak * 0.5 * (1 - np.cos(np.pi * (t_arr[m1] - t0) / (t1 - t0)))
        out[m2] = peak
        out[m3] = peak * 0.5 * (1 + np.cos(np.pi * (t_arr[m3] - t2) / (t3 - t2)))
        return out

    delta += cosine_pulse(t, 26.0, 28.0, 44.0, 46.0, peak=0.015)

    # Mid-corner tightening 28-32 s: adds another 0.015 rad on top → peak 0.030
    # rad (~1.7° road wheel). At v ≈ 20 m/s this gives yaw rate ~ 0.21 rad/s
    # = 12°/s and lateral G ~ 4.2 m/s² — close to the ±5 m/s² edge of ST's
    # linear-honest band. Deliberate teaching beat.
    delta += cosine_pulse(t, 28.0, 29.0, 31.0, 32.0, peak=0.015)

    # ---- Longitudinal acceleration (m/s²) ------------------------------------
    a = np.zeros(N)
    # Brake 22-30 s at -0.625 m/s² → 25 → 20 m/s entering the off-ramp
    brake_mask = (t >= 22.0) & (t < 30.0)
    a[brake_mask] = -0.625

    # ---- Steering rate (derived) --------------------------------------------
    delta_dot = np.gradient(delta, dt)

    return KSDriverInputs(t=t, delta_dot=delta_dot, a=a, delta_meas=delta)


if __name__ == "__main__":
    inp = make_demo_inputs()
    print(f"Generated {len(inp.t)} samples over {inp.t[-1]:.1f} s")
    print(f"  peak |delta|      = {np.abs(inp.delta_meas).max():.4f} rad")
    print(f"  peak |delta_dot|  = {np.abs(inp.delta_dot).max():.4f} rad/s")
    print(f"  min/max a         = {inp.a.min():+.2f} / {inp.a.max():+.2f} m/s²")
