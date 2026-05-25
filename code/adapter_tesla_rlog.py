"""Tesla rlog → KS driver inputs adapter (real data path).

Reads decoded CAN frames out of a commaCarSegments Tesla rlog and produces:

  - KSDriverInputs        — (t, delta_dot, a, delta_meas) at a uniform rate
  - TeslaRealMeasurements — the rest of the decoded signals (vehicle speed,
                            accel pedal %, drive-inverter torque) for plotting,
                            audit, or richer model variants.

Provenance reality check (from inspecting one rlog of this dataset):

  - sensorEvents / liveLocationKalman / carState are **NOT in this log**.
    The comma3 was logging passively from the bus without controlsd/locationd
    running. We have only `can`, `pandaStates`, and `carParams`.
  - That means every signal — INPUT and TRUTH — comes from decoded Tesla CAN.
    There is no separately-trustworthy "comma-hardware lane" in this dataset.
  - The Tesla party DBC openpilot ships does NOT expose Tesla's internal IMU
    (yaw rate, lateral G are reverse-engineered as quality-flag bits only).
    So the workshop's "compare predicted ψ̇ to measured ψ̇" beat is gated on
    either (a) decoding the IMU-bearing message ourselves later, or (b)
    estimating effective ψ̇ from wheel-speed differential / steering geometry.
    This file deliberately does NOT fake a truth channel.

What we DO have, end-to-end:

  - Steering wheel angle    (SCCM_steeringAngle, 0x129, bus 2, 100 Hz, deg)
  - Vehicle speed           (DI_vehicleSpeed,    0x257, bus 0,  50 Hz, kph)
  - Accelerator pedal %     (DI_accelPedalPos,   0x118, bus 0, 100 Hz, %)
  - Brake pedal state       (DI_brakePedalState, 0x118, bus 0, 100 Hz, enum)
  - Drive-inverter torque   (DI_torqueActual,    0x108, bus 0, 100 Hz, Nm)
  - Per-wheel speeds        (ESP_wheelSpeeds,    0x175, bus 0, 100 Hz, km/h)

Longitudinal acceleration is **derived** from the smoothed numerical derivative
of vehicle speed. That is honest — calling it "measured" would not be.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from rlog_reader import iter_events

# Imports lazily inside functions so the module can be imported without these
# present (e.g. if someone just wants to read the docstrings).


# ---------- DBC + bus constants ----------------------------------------------

_HERE = Path(__file__).resolve().parent
DEFAULT_DBC = _HERE / "_schema" / "dbc" / "tesla_model3_party.dbc"

# Tesla party-bus addresses we read.
ADDR_DI_TORQUE = 0x108     # DI_torque              — drive inverter torque (bus 0)
ADDR_DI_SYSTEM = 0x118     # DI_systemStatus        — accel pedal, brake state (bus 0)
ADDR_STEER     = 0x129     # SCCM_steeringAngle     — steering wheel angle (bus 2)
ADDR_ESP_B     = 0x155     # ESP_B                  — pulse counts, vehicleSpeed (bus 0)
ADDR_WSPD      = 0x175     # ESP_wheelSpeeds        — per-wheel speeds (bus 0)
ADDR_DI_SPEED  = 0x257     # DI_speed               — DI_vehicleSpeed (bus 0)

# We accept either the raw bus (0 = powertrain, 2 = chassis) or any bus —
# the panda's logger duplicates frames onto bus 128/130 with a flag bit set
# and we don't want to count those duplicates.
RAW_BUSES = {0, 2}


# ---------- Output dataclasses -----------------------------------------------

@dataclass
class TeslaRealMeasurements:
    """Decoded + resampled signals from one rlog, uniform 50 Hz grid."""
    t: np.ndarray                       # [s], shape (N,)
    delta_wheel_deg: np.ndarray         # steering wheel angle [deg]
    delta_road_rad: np.ndarray          # steering wheel / steerRatio [rad]
    v_mps: np.ndarray                   # vehicle speed [m/s]
    a_long_mps2: np.ndarray             # derived from smoothed dv/dt [m/s²]
    accel_pedal_pct: np.ndarray         # driver accel pedal position [%]
    brake_pedal_state: np.ndarray       # brake state enum, raw int
    di_torque_actual_nm: np.ndarray     # drive-inverter actual torque [Nm]
    wheel_speeds_kph: np.ndarray        # shape (N, 4): FL, FR, RL, RR


# ---------- Helpers ----------------------------------------------------------

def _frame_iter(rlog_path: Path, addrs: Iterable[int]):
    """Yield (t_ns, addr, dat) for frames on a raw bus whose addr is in addrs."""
    want = set(addrs)
    t0 = None
    for ev in iter_events(rlog_path):
        if ev.service != "can":
            continue
        t = ev.log_mono_time_ns
        if t0 is None:
            t0 = t
        for fr in ev.payload:
            if fr.src in RAW_BUSES and fr.address in want:
                yield t - t0, fr.address, bytes(fr.dat)


def _decode_series(records, addr: int, signal: str, db):
    msg = db.get_message_by_frame_id(addr)
    ts, ys = [], []
    for t_ns, dat in records[addr]:
        try:
            val = msg.decode(dat)[signal]
        except Exception:
            continue
        # cantools returns NamedSignalValue for VAL_-mapped enums — coerce to
        # raw int via .value. Plain floats fall through.
        if hasattr(val, "value"):
            y = float(val.value)
        else:
            try:
                y = float(val)
            except (TypeError, ValueError):
                continue
        ts.append(t_ns * 1e-9)
        ys.append(y)
    return np.asarray(ts), np.asarray(ys, dtype=float)


def _resample(t_grid: np.ndarray, t: np.ndarray, y: np.ndarray) -> np.ndarray:
    if len(t) < 2:
        return np.full_like(t_grid, np.nan)
    return np.interp(t_grid, t, y)


def _lowpass(y: np.ndarray, fs: float, cutoff_hz: float) -> np.ndarray:
    from scipy.signal import butter, filtfilt
    b, a = butter(2, cutoff_hz / (fs / 2.0))
    return filtfilt(b, a, y)


# ---------- Public API -------------------------------------------------------

def load_segment_measurements(
    rlog_path: Path,
    sample_rate_hz: float = 50.0,
    dbc_path: Path | None = None,
    crop_edges_s: float = 1.0,
) -> TeslaRealMeasurements:
    """Decode one rlog into a uniform-rate measurement dataframe.

    Pipeline:
      1. iter_events → bucket CAN frames by address
      2. cantools decode every frame
      3. resample each signal linearly onto a sample_rate_hz grid
      4. derive a_long from low-pass-filtered dv/dt
      5. crop the first and last `crop_edges_s` of the segment
    """
    import cantools

    db = cantools.database.load_file(str(dbc_path or DEFAULT_DBC))

    addrs = (ADDR_STEER, ADDR_DI_SPEED, ADDR_DI_SYSTEM,
             ADDR_DI_TORQUE, ADDR_WSPD)
    records = {a: [] for a in addrs}
    for t_ns, addr, dat in _frame_iter(Path(rlog_path), addrs):
        records[addr].append((t_ns, dat))

    # Decode each signal we want.
    t_st, steer_deg     = _decode_series(records, ADDR_STEER,     "SCCM_steeringAngle",  db)
    t_v,  v_kph         = _decode_series(records, ADDR_DI_SPEED,  "DI_vehicleSpeed",     db)
    t_a,  accel_pct     = _decode_series(records, ADDR_DI_SYSTEM, "DI_accelPedalPos",    db)
    t_b,  brake_st      = _decode_series(records, ADDR_DI_SYSTEM, "DI_brakePedalState",  db)
    t_q,  tq_nm         = _decode_series(records, ADDR_DI_TORQUE, "DI_torqueActual",     db)
    t_w, w_fl_kph       = _decode_series(records, ADDR_WSPD,      "ESP_wheelSpeedFrL",   db)
    _,   w_fr_kph       = _decode_series(records, ADDR_WSPD,      "ESP_wheelSpeedFrR",   db)
    _,   w_rl_kph       = _decode_series(records, ADDR_WSPD,      "ESP_wheelSpeedReL",   db)
    _,   w_rr_kph       = _decode_series(records, ADDR_WSPD,      "ESP_wheelSpeedReR",   db)

    if len(steer_deg) < 100 or len(v_kph) < 50:
        raise RuntimeError(
            f"Segment {rlog_path} decoded too few frames: "
            f"steer={len(steer_deg)} speed={len(v_kph)}. "
            "Likely partial rlog or wrong DBC bus."
        )

    # Common time horizon — the intersection of available windows
    t_start = max(t_st.min(), t_v.min(), t_a.min(), t_q.min(), t_w.min()) + crop_edges_s
    t_end   = min(t_st.max(), t_v.max(), t_a.max(), t_q.max(), t_w.max()) - crop_edges_s
    if t_end - t_start < 5.0:
        raise RuntimeError(f"Segment {rlog_path} too short after edge crop")

    # 50 Hz grid
    dt = 1.0 / sample_rate_hz
    t_grid = np.arange(t_start, t_end, dt)

    steer_r = _resample(t_grid, t_st, steer_deg)
    v_r_kph = _resample(t_grid, t_v,  v_kph)
    a_r     = _resample(t_grid, t_a,  accel_pct)
    b_r     = _resample(t_grid, t_b,  brake_st)
    q_r     = _resample(t_grid, t_q,  tq_nm)
    w_r = np.column_stack([
        _resample(t_grid, t_w, w_fl_kph),
        _resample(t_grid, t_w, w_fr_kph),
        _resample(t_grid, t_w, w_rl_kph),
        _resample(t_grid, t_w, w_rr_kph),
    ])

    v_mps = v_r_kph / 3.6
    # a_long from low-pass-filtered dv/dt at 5 Hz cutoff
    v_smooth = _lowpass(v_mps, sample_rate_hz, cutoff_hz=5.0)
    a_long = np.gradient(v_smooth, t_grid)

    # delta_road from steer / steerRatio (steerRatio loaded by caller via
    # parameters.TESLA_MODEL_3.i_s — but we compute the per-Hz quantity here
    # using the openpilot canonical 12.0 to keep this function self-contained;
    # callers that want a different steerRatio can recompute from delta_wheel_deg).
    OPENPILOT_TESLA_STEER_RATIO = 12.0
    delta_road = np.deg2rad(steer_r) / OPENPILOT_TESLA_STEER_RATIO

    return TeslaRealMeasurements(
        t=t_grid - t_grid[0],
        delta_wheel_deg=steer_r,
        delta_road_rad=delta_road,
        v_mps=v_mps,
        a_long_mps2=a_long,
        accel_pedal_pct=a_r,
        brake_pedal_state=b_r,
        di_torque_actual_nm=q_r,
        wheel_speeds_kph=w_r,
    )
