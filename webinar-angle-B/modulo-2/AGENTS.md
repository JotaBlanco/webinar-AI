# AGENTS.md

You are working on a vehicle dynamics modelling project.

## Project purpose

This project explores the comparison between simulated vehicle dynamics models and real driving data. The team is interested in understanding how well classical physics models capture real-world behaviour and where they fall short. The work has applications in autonomous driving research, advanced driver-assistance systems (ADAS), motorsport analytics, vehicle development, calibration of digital twins, and broader sim-to-real correlation efforts across the automotive sector. The team includes vehicle dynamics engineers with motorsport backgrounds, data scientists with experience in residual learning and physics-plus-data hybrid modelling, and software engineers experienced in data infrastructure and streaming systems. Decisions in this project should always consider the production deployment perspective — i.e. models are not just for research but eventually need to run in real-time or near-real-time on vehicle compute or edge infrastructure. We tend to favour interpretable physics-based approaches over pure black-box machine learning, especially when the underlying domain has strong first-principles knowledge.

## Build / run

- Python 3.11+ environment.
- Dependencies typically include numpy, scipy, matplotlib, pandas; for CAN bus decoding cantools and pycapnp are required; for compressed log handling zstandard.
- Code is generally run by invoking python scripts directly. Output figures and CSVs are written next to the scripts or to a sibling data directory depending on the script.

## Vehicle dynamics conventions

This section captures the conventions the team uses across all vehicle dynamics work. These conventions are non-negotiable and apply to every model, every analysis, every plot, and every report.

### Coordinate frames and sign conventions

The vehicle body frame is defined with the X axis pointing forward (longitudinal, in the direction of travel when the steering is centred), the Y axis pointing to the *left* of the vehicle (lateral, positive towards the driver's left), and the Z axis pointing *up* (vertical, opposite to gravity). This is the ISO 8855 convention and is the convention used across the automotive industry for vehicle dynamics work — note that it differs from the SAE J670 convention which has Y pointing right and Z pointing down. Aerospace conventions (e.g. NED — North-East-Down) are sometimes seen in autonomous driving codebases and should be avoided; if a tool uses NED, the data should be converted to ISO 8855 before any model is applied.

Heading (yaw angle, ψ) is measured *positive counterclockwise when viewed from above*, with zero pointing in the direction of the world X axis. Yaw rate (ψ̇, sometimes written `r` or `psi_dot`) is the time derivative of heading and is therefore also positive counterclockwise. A left turn produces a positive yaw rate; a right turn produces a negative yaw rate. The sign of the steering wheel angle should be consistent: a counterclockwise rotation of the steering wheel (as seen by the driver) is positive and produces a left turn — but be aware that some manufacturers' CAN signals invert this convention internally and a sign flip may be needed at the adapter layer.

Lateral acceleration (a_y, sometimes a_lat or Ay) follows the body frame Y axis convention: positive when accelerating to the left. For a vehicle in a steady-state left turn, the lateral acceleration is positive and points towards the centre of the turn (which is to the left of the vehicle). Centripetal acceleration in a body frame is therefore positive in a left turn and negative in a right turn — do not confuse this with the world-frame centripetal acceleration which always points from the vehicle towards the instantaneous centre of rotation.

Steering angle is typically reported in two forms: the steering wheel angle (the angle of the steering wheel as turned by the driver, in degrees) and the road wheel angle or "front wheel steer angle" (the actual angle of the front road wheels relative to the vehicle longitudinal axis, in radians for modelling). The steering ratio relates the two: road wheel angle = steering wheel angle / steering ratio. Steering ratios vary by vehicle and even by speed for vehicles with variable-ratio steering racks; typical passenger car values are between 12:1 (sporty) and 18:1 (luxury/SUV).

### Units

All quantities are expressed in SI units unless explicitly stated. The exceptions are:
- Steering wheel angle (degrees, because it is the natural unit in which it is measured and reported by the CAN bus on most production vehicles).
- Vehicle speed when reported in human-readable contexts (km/h is common in non-US datasets; mph in US datasets).
- Tyre pressures (psi or bar depending on the team).
- For modelling: every angular quantity is in radians; every speed in m/s; every acceleration in m/s²; every distance in metres; every mass in kg; every moment of inertia in kg·m²; every cornering stiffness in N/rad; every time in seconds.

### Vehicle dynamics model fidelity ladder

The team works across a fidelity ladder of vehicle dynamics models. From lowest to highest fidelity:

1. **Point-mass model.** No body, no tyres, no slip. Used for very high-level trajectory planning where geometric feasibility is the only concern. Not relevant for this project.
2. **Kinematic single-track (KS) model.** The "driving-school" model. The car is a rigid rod of length L (the wheelbase) with a single front wheel and a single rear wheel. There is no tyre, no slip, no lateral force balance — wherever the front wheel points, the car follows. The KS model has 5 states: position (x, y), heading (ψ), longitudinal speed (v), and steering angle (δ).
3. **Single-track dynamic model (ST).** Adds tyre cornering stiffness (linear regime), lateral force balance, and the slip angle. The car now resists lateral motion based on tyre cornering stiffness. The states are typically (x, y, ψ, v, δ, β, ψ̇) where β is the sideslip angle and ψ̇ is the yaw rate.
4. **Multi-body single-track with non-linear tyres.** Adds non-linear tyre behaviour (Pacejka magic formula or similar), tyre saturation, weight transfer, etc.
5. **Full multi-body vehicle dynamics simulation.** Out of scope for this project; would require commercial tools (CarSim, Adams Car, IPG CarMaker).

### Time alignment and sampling rates

CAN bus signals on production vehicles are sampled at varying rates depending on the message: typically 100 Hz for chassis dynamics signals (yaw rate, lateral acceleration, longitudinal acceleration, wheel speeds), 50 Hz for steering signals, and 10-20 Hz for slower signals. The IMU sensor on openpilot devices samples at 100 Hz. The GPS sample rate is typically 10 Hz. When comparing signals or feeding them into a model, all signals should be resampled to a common time grid.

### Naming conventions

Variables in code should use lowercase with underscores. Greek letters are spelled out (delta, psi, beta, omega) rather than encoded as unicode. Time series arrays are named with the underlying physical quantity followed by an underscore and the unit suffix where ambiguous (e.g. `delta_rad`, `v_mps`, `a_y_mps2`). The "_rads" suffix denotes radians per second (so `yaw_rate_rads` is in rad/s, not rad). Predicted-vs-measured pairs are suffixed `_pred` and `_meas` respectively. Residuals are `meas - pred` by convention. Files for time-series data are typically CSVs at 50 Hz with one header row.

## Known traps

- Don't confuse ISO 8855 with SAE J670 — sign of Y axis differs.
- Don't confuse steering wheel angle (degrees) with road wheel angle (radians, divided by steering ratio).
- Don't trust GPS heading at low speeds — it is noisy below ~3 m/s. Use IMU-integrated heading instead.
- Don't compare predicted yaw rate against measured yaw rate without first checking the sign convention is consistent on both sides.
- Don't assume the cornering stiffness from a vehicle manufacturer's datasheet matches the tyres actually fitted.

## Skills inventory

(No skills available.)

## Evals

(No evals.)

## References

(No references.)
