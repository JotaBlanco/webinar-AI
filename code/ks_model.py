"""KS — Kinematic Single-Track model.

Bottom rung of the CommonRoad fidelity ladder. The "driving-school" model:
a rigid rod of length L with mass m at its centre, no tyre, no slip — wherever
the front wheel points, the car goes.

State:  x = (x, y, psi, v, delta)
Input:  u = (delta_dot, a)
Param:  p.L, p.delta_max, p.delta_dot_max, p.a_min, p.a_max

Equations (from ../models.md § "KS — Kinematic Single-Track"):

    dx/dt      = v · cos(psi)
    dy/dt      = v · sin(psi)
    dpsi/dt    = (v / L) · tan(delta)
    dv/dt      = a
    ddelta/dt  = delta_dot

Yaw rate (psi_dot) and lateral acceleration (a_y) are not states; they are
derived outputs:

    psi_dot = (v / L) · tan(delta)
    a_y     = v · psi_dot

This is the entire model. There is no force balance because no forces are
computed — the car is *assumed* to follow its wheels exactly. See
../models.md § "Lies told" for what this means in practice.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np

from parameters import TeslaModel3KS


# ---------- State and output dataclasses -------------------------------------

@dataclass
class KSState:
    """Five-component state of the KS model."""
    x: float       # world x [m]
    y: float       # world y [m]
    psi: float     # heading [rad]
    v: float       # speed [m/s]
    delta: float   # steering angle (road wheel) [rad]

    def as_array(self) -> np.ndarray:
        return np.array([self.x, self.y, self.psi, self.v, self.delta])

    @classmethod
    def from_array(cls, a: np.ndarray) -> "KSState":
        return cls(*a.tolist())


@dataclass
class KSDriverInputs:
    """Time-series of driver inputs at a fixed sample rate.

    All arrays share the same length and the same time grid `t`.

    `delta_meas` is the measured road-wheel angle (steering-wheel angle /
    steering ratio). If supplied with `clamp_delta_to_measured=True`, the
    integrator overrides the state's delta at each step.

    `v_meas` is the measured longitudinal speed (m/s, from the wheel-speed
    CAN signal). If supplied with `clamp_v_to_measured=True`, the integrator
    overrides the state's `v` at each step — turning KS into a *speed-known*
    lateral-dynamics model rather than a fully open-loop integrator. This is
    the workshop's primary mode (see ../models.md § "Speed-known framing").
    """
    t: np.ndarray              # [s], shape (N,)
    delta_dot: np.ndarray      # [rad/s], shape (N,)
    a: np.ndarray              # [m/s²], shape (N,)
    delta_meas: np.ndarray | None = None  # [rad], shape (N,), optional
    v_meas: np.ndarray | None = None      # [m/s], shape (N,), optional


# ---------- The ODE -----------------------------------------------------------

def ks_dynamics(state: np.ndarray, u: np.ndarray, p: TeslaModel3KS) -> np.ndarray:
    """f(x, u; p) for the KS model. Returns dx/dt as a (5,) array.

    state = [x, y, psi, v, delta]
    u     = [delta_dot, a]
    """
    _, _, psi, v, delta = state
    delta_dot, a = u

    # Apply actuator limits (saturation at the input level, not in the integrator).
    delta_dot = np.clip(delta_dot, -p.delta_dot_max, p.delta_dot_max)
    a = np.clip(a, p.a_min, p.a_max)

    return np.array([
        v * np.cos(psi),          # dx/dt
        v * np.sin(psi),          # dy/dt
        (v / p.L) * np.tan(delta),  # dpsi/dt
        a,                          # dv/dt
        delta_dot,                  # ddelta/dt
    ])


# ---------- Integrator --------------------------------------------------------

def rk4_step(f: Callable, x: np.ndarray, u: np.ndarray, dt: float, p) -> np.ndarray:
    """Classical 4th-order Runge-Kutta. f signature: f(x, u; p) -> dx/dt."""
    k1 = f(x, u, p)
    k2 = f(x + 0.5 * dt * k1, u, p)
    k3 = f(x + 0.5 * dt * k2, u, p)
    k4 = f(x + dt * k3, u, p)
    return x + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


# ---------- Simulator ---------------------------------------------------------

@dataclass
class KSTrajectory:
    """The output of a KS integration. All arrays have shape (N,)."""
    t: np.ndarray         # [s]
    x: np.ndarray         # [m]
    y: np.ndarray         # [m]
    psi: np.ndarray       # [rad]
    v: np.ndarray         # [m/s]
    delta: np.ndarray     # [rad]
    psi_dot: np.ndarray   # [rad/s] — derived output
    a_y: np.ndarray       # [m/s²] — derived output


def simulate_ks(
    inputs: KSDriverInputs,
    initial: KSState,
    p: TeslaModel3KS,
    clamp_delta_to_measured: bool = False,
    clamp_v_to_measured: bool = False,
) -> KSTrajectory:
    """Integrate the KS model forward over the input time series.

    Parameters
    ----------
    inputs : KSDriverInputs
        Driver-input traces on a uniform time grid.
    initial : KSState
        Initial state at t = inputs.t[0].
    p : TeslaModel3KS
        Vehicle parameters.
    clamp_delta_to_measured : bool
        If True and `inputs.delta_meas` is not None, the state's delta is
        overridden by the measured value at every step. The model is no
        longer being driven by steering *rate*; it is being given the
        measured steering *angle* directly.
    clamp_v_to_measured : bool
        If True and `inputs.v_meas` is not None, the state's longitudinal
        speed is overridden by the measured value at every step. This is the
        workshop's **speed-known** mode: the longitudinal channel of the
        model is no longer being predicted — it is being given. The model's
        job becomes predicting *only* the lateral response (`ψ̇`, position,
        heading) given measured `(v, δ)`. See ../models.md § "Speed-known
        framing" for why this is the right scope for the workshop.
    """
    t = inputs.t
    N = len(t)
    if N < 2:
        raise ValueError("Need at least two timesteps")

    clamp_d = clamp_delta_to_measured and inputs.delta_meas is not None
    clamp_v = clamp_v_to_measured     and inputs.v_meas     is not None

    X = np.zeros((N, 5))
    X[0] = initial.as_array()
    if clamp_d:
        X[0, 4] = inputs.delta_meas[0]
    if clamp_v:
        X[0, 3] = inputs.v_meas[0]

    for k in range(N - 1):
        dt = t[k + 1] - t[k]
        u_k = np.array([inputs.delta_dot[k], inputs.a[k]])
        X[k + 1] = rk4_step(ks_dynamics, X[k], u_k, dt, p)
        if clamp_d:
            X[k + 1, 4] = inputs.delta_meas[k + 1]
        if clamp_v:
            X[k + 1, 3] = inputs.v_meas[k + 1]

    psi_dot = (X[:, 3] / p.L) * np.tan(X[:, 4])  # (v / L) · tan(delta)
    a_y = X[:, 3] * psi_dot                       # v · psi_dot

    return KSTrajectory(
        t=t,
        x=X[:, 0], y=X[:, 1], psi=X[:, 2], v=X[:, 3], delta=X[:, 4],
        psi_dot=psi_dot, a_y=a_y,
    )


if __name__ == "__main__":
    # Smoke test: drive in a circle at constant speed and constant steering.
    # The car should trace a circle of radius L / tan(delta).
    from parameters import TESLA_MODEL_3

    T = 30.0
    dt = 0.01
    N = int(T / dt)
    t = np.arange(N) * dt

    delta_const = 0.05  # 0.05 rad ≈ 2.9° at the road wheel
    inputs = KSDriverInputs(
        t=t,
        delta_dot=np.zeros(N),
        a=np.zeros(N),
        delta_meas=np.full(N, delta_const),
    )

    initial = KSState(x=0.0, y=0.0, psi=0.0, v=20.0, delta=delta_const)
    traj = simulate_ks(inputs, initial, TESLA_MODEL_3, clamp_delta_to_measured=True)

    expected_R = TESLA_MODEL_3.L / np.tan(delta_const)
    final_dist_from_origin = np.sqrt(traj.x[-1] ** 2 + traj.y[-1] ** 2)
    print(f"Expected circle radius: {expected_R:.2f} m")
    print(f"Observed radius (proxy: max|x| in first 1/4 lap): {traj.x.max():.2f} m")
    print(f"Final yaw rate: {traj.psi_dot[-1]:.4f} rad/s "
          f"(expected: {traj.v[-1] / expected_R:.4f} rad/s)")
