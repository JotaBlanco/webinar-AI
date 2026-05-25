"""Lateral-fidelity corrections for the speed-known KS pipeline.

Two corrections, both addressing residuals seen in baseline Ford sim CSVs:

* H1 — `estimate_yaw_bias`: per-segment yaw-rate sensor zero-offset, estimated
  from straight-line samples and subtracted from the measured channel.
* H3 — `apply_understeer_correction`: divides the KS yaw-rate prediction by
  `(1 + K_u * v^2)` to model steady-state tyre compliance. `K_u` is computed
  analytically from `MachEST`/`F150LightningST` parameters via
  `understeer_gradient(p_st)`.

All functions are pure; no I/O.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# Add code/ to import path for parameters
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))


def estimate_yaw_bias(
    yaw_meas_rads: np.ndarray,
    delta_road_rad: np.ndarray,
    v_mps: np.ndarray,
    delta_thresh_rad: float = 0.005,   # ~0.3 deg road wheel
    yaw_thresh_rads: float = 0.02,     # ~1.1 deg/s
    v_min_mps: float = 3.0,
    min_samples: int = 50,
) -> float:
    """Estimate constant yaw-rate sensor bias from straight-line samples.

    A straight-line sample has near-zero steering AND near-zero measured yaw
    AND nontrivial forward speed (excludes parking/stop where signals are
    noisy). The bias is the median yaw_meas over that mask — robust to the
    occasional turn-onset sample slipping through. If fewer than `min_samples`
    qualify, returns 0.0 and prints a warning to stderr.

    Returns
    -------
    b_hat : float
        Estimated bias in rad/s. Subtract from `yaw_meas_rads` to debias.
    """
    mask = (
        (np.abs(delta_road_rad) < delta_thresh_rad)
        & (np.abs(yaw_meas_rads) < yaw_thresh_rads)
        & (v_mps > v_min_mps)
    )
    n = int(mask.sum())
    if n < min_samples:
        print(
            f"  ! yaw-bias estimate: only {n} straight-line samples "
            f"(need >={min_samples}); returning 0.0",
            file=sys.stderr,
        )
        return 0.0
    return float(np.median(yaw_meas_rads[mask]))


def understeer_gradient(p_st) -> float:
    """Analytic understeer gradient from linear bicycle (ST) parameters.

    K_u = (m / L^2) * (l_r / C_alpha_f - l_f / C_alpha_r)

    Units: s^2 / m^2 (so K_u * v^2 is dimensionless).
    Positive => understeer (yaw rate falls below KS prediction with v).
    For openpilot Ford carParams the platforms come out marginally
    understeering — consistent with the F-150 turn-gain ratio 0.851 < 1.
    """
    L = p_st.L
    return (p_st.m / L**2) * (p_st.l_r / p_st.C_alpha_f - p_st.l_f / p_st.C_alpha_r)


def apply_understeer_correction(
    psi_dot_ks: np.ndarray, v_mps: np.ndarray, K_u: float
) -> np.ndarray:
    """psi_dot_corrected = psi_dot_KS / (1 + K_u * v^2).

    Captures the steady-state portion of the linear single-track yaw-rate
    response. At v=0 it is identity; at highway speed for an understeering
    car, it shrinks the KS over-prediction.
    """
    return psi_dot_ks / (1.0 + K_u * v_mps**2)


if __name__ == "__main__":
    # Smoke test: print K_u for the two Ford platforms.
    from parameters import MACH_E, F150_LIGHTNING

    for label, p in [("MachE", MACH_E), ("F150", F150_LIGHTNING)]:
        K_u = understeer_gradient(p)
        v = np.array([5.0, 15.0, 25.0])
        factor = 1.0 + K_u * v**2
        print(f"{label}: K_u = {K_u:.6e}   factor(1+K_u v^2) at v={v.tolist()}: {factor.tolist()}")
