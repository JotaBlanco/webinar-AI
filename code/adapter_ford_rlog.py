"""Ford rlog → KS driver inputs adapter (real data path).

Reads decoded CAN frames out of a commaCarSegments Ford rlog (Mustang Mach-E or
F-150 Lightning, same DBC) and produces:

  - KSDriverInputs          — (t, delta_dot, a, delta_meas) at 50 Hz
  - FordRealMeasurements    — the rest of the decoded signals, INCLUDING the
                              IMU-grade yaw rate that Tesla rlogs do not
                              expose: `Yaw_Data_FD1.VehYaw_W_Actl` (rad/s).

Provenance reality check (from probing the rlogs themselves):

  - Same envelope as the Tesla rlogs: only `can`, `pandaStates`, `carParams`.
    The comma3 was logging passively from the bus; controlsd/locationd were
    not running. So there is no `carState` / `sensorEvents` etc. — every
    signal comes from decoded Ford CAN.
  - BUT — Ford ports openpilot's full carstate.py with `ret.yawRate` populated
    from `Yaw_Data_FD1.VehYaw_W_Actl`. That signal IS in the open Ford DBC,
    so the workshop's "compare predicted ψ̇ to measured ψ̇" beat lands here in
    a way it could not on Tesla.
  - The Ford DBC also exposes `VehLatComp_A_Actl` (lateral acc, m/s²) and
    `VehLongComp_A_Actl` (longitudinal acc, m/s²) on `BrakeSnData_3`. We use
    the long-acc directly as KS's `a` input rather than deriving from dv/dt.
    The lat-acc is a second validation channel alongside yaw rate.
  - Bus filter: bus 0 is the powertrain bus; the panda mirrors every frame on
    bus 130. We accept bus 0 only.

What we have, end-to-end (Mach-E + Lightning, same DBC):

  Address  Bus  Message              Signal                 Units  Role
  -------  ---  -------------------  ---------------------  -----  ------
   0x07E   0    SteeringPinion_Data  StePinComp_An_Est       deg    INPUT  (wheel angle)
   0x415   0    BrakeSysFeatures     Veh_V_ActlBrk           kph    INPUT  (speed)
   0x091   0    Yaw_Data_FD1         VehYaw_W_Actl           rad/s  TRUTH  (yaw rate)
   0x077   0    BrakeSnData_3        VehLongComp_A_Actl      m/s²   INPUT  (a_long)
   0x077   0    BrakeSnData_3        VehLatComp_A_Actl       m/s²   TRUTH  (a_y)
   0x077   0    BrakeSnData_3        VehOverGnd_V_Est        kph    extra
   0x204   0    EngVehicleSpThrottle ApedPos_Pc_ActlArb      %      extra
   0x165   0    EngBrakeData         BpedDrvAppl_D_Actl      enum   extra
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from rlog_reader import iter_events

_HERE = Path(__file__).resolve().parent
DEFAULT_DBC = _HERE / "_schema" / "dbc" / "ford_lincoln_base_pt.dbc"

# Ford CAN addresses we read.
ADDR_STEER  = 0x07E    # SteeringPinion_Data
ADDR_YAW    = 0x091    # Yaw_Data_FD1
ADDR_BRAKE3 = 0x077    # BrakeSnData_3       (lat-acc, long-acc, yaw-deg/s)
ADDR_SPEED  = 0x415    # BrakeSysFeatures    (Veh_V_ActlBrk)
ADDR_APED   = 0x204    # EngVehicleSpThrottle
ADDR_BPED   = 0x165    # EngBrakeData

# Powertrain bus only — panda mirrors on bus 130, we ignore those duplicates.
RAW_BUSES = {0}


@dataclass
class FordRealMeasurements:
    """Decoded + resampled signals from one Ford rlog, uniform 50 Hz grid."""
    t: np.ndarray                       # [s], shape (N,)
    delta_wheel_deg: np.ndarray         # steering wheel angle [deg]
    delta_road_rad: np.ndarray          # steering wheel / steerRatio [rad]
    v_mps: np.ndarray                   # vehicle speed [m/s]
    a_long_mps2: np.ndarray             # measured longitudinal acc [m/s²]
    a_lat_mps2: np.ndarray              # measured lateral acc [m/s²]      ← TRUTH
    yaw_rate_rads: np.ndarray           # measured yaw rate [rad/s]        ← TRUTH
    accel_pedal_pct: np.ndarray         # driver accel pedal position [%]
    brake_pressed: np.ndarray           # bool / int (1 = braking)
    v_ovrgnd_mps: np.ndarray            # over-ground speed estimate [m/s]


def _frame_iter(rlog_path: Path, addrs: Iterable[int]):
    """Yield (t_ns_since_first, addr, dat) for matching frames on RAW_BUSES."""
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


def load_segment_measurements(
    rlog_path: Path,
    steer_ratio: float,
    sample_rate_hz: float = 50.0,
    dbc_path: Path | None = None,
    crop_edges_s: float = 1.0,
) -> FordRealMeasurements:
    """Decode one Ford rlog into a uniform-rate measurement dataframe.

    `steer_ratio` is taken from the platform's parameter set
    (parameters.MACH_E.i_s or parameters.F150_LIGHTNING.i_s) rather than
    hard-coded — both Ford variants run ~17:1 racks but they are not identical.
    """
    import cantools

    db = cantools.database.load_file(str(dbc_path or DEFAULT_DBC))

    addrs = (ADDR_STEER, ADDR_YAW, ADDR_BRAKE3, ADDR_SPEED, ADDR_APED, ADDR_BPED)
    records = {a: [] for a in addrs}
    for t_ns, addr, dat in _frame_iter(Path(rlog_path), addrs):
        records[addr].append((t_ns, dat))

    t_st, steer_deg = _decode_series(records, ADDR_STEER,  "StePinComp_An_Est",  db)
    t_y,  yaw_rads  = _decode_series(records, ADDR_YAW,    "VehYaw_W_Actl",      db)
    t_lo, a_long    = _decode_series(records, ADDR_BRAKE3, "VehLongComp_A_Actl", db)
    t_la, a_lat     = _decode_series(records, ADDR_BRAKE3, "VehLatComp_A_Actl",  db)
    t_og, v_og_kph  = _decode_series(records, ADDR_BRAKE3, "VehOverGnd_V_Est",   db)
    t_v,  v_kph     = _decode_series(records, ADDR_SPEED,  "Veh_V_ActlBrk",      db)
    t_a,  accel_pct = _decode_series(records, ADDR_APED,   "ApedPos_Pc_ActlArb", db)
    t_b,  bped      = _decode_series(records, ADDR_BPED,   "BpedDrvAppl_D_Actl", db)

    if len(steer_deg) < 100 or len(v_kph) < 50 or len(yaw_rads) < 100:
        raise RuntimeError(
            f"Segment {rlog_path} decoded too few frames: "
            f"steer={len(steer_deg)} speed={len(v_kph)} yaw={len(yaw_rads)}. "
            "Likely partial rlog or wrong DBC bus."
        )

    t_start = max(t_st.min(), t_y.min(), t_lo.min(), t_la.min(),
                  t_v.min(), t_a.min(), t_b.min()) + crop_edges_s
    t_end   = min(t_st.max(), t_y.max(), t_lo.max(), t_la.max(),
                  t_v.max(), t_a.max(), t_b.max()) - crop_edges_s
    if t_end - t_start < 5.0:
        raise RuntimeError(f"Segment {rlog_path} too short after edge crop")

    dt = 1.0 / sample_rate_hz
    t_grid = np.arange(t_start, t_end, dt)

    steer_r  = _resample(t_grid, t_st, steer_deg)
    yaw_r    = _resample(t_grid, t_y,  yaw_rads)
    alon_r   = _resample(t_grid, t_lo, a_long)
    alat_r   = _resample(t_grid, t_la, a_lat)
    v_og_r   = _resample(t_grid, t_og, v_og_kph)
    v_r      = _resample(t_grid, t_v,  v_kph)
    aped_r   = _resample(t_grid, t_a,  accel_pct)
    bped_r   = _resample(t_grid, t_b,  bped)

    # Light low-pass on the raw lateral & long acceleration channels — ABS
    # publishes at 50 Hz with 1-LSB quantisation that creates visual stairsteps.
    alon_smooth = _lowpass(alon_r, sample_rate_hz, cutoff_hz=5.0)
    alat_smooth = _lowpass(alat_r, sample_rate_hz, cutoff_hz=5.0)

    delta_road = np.deg2rad(steer_r) / steer_ratio

    return FordRealMeasurements(
        t=t_grid - t_grid[0],
        delta_wheel_deg=steer_r,
        delta_road_rad=delta_road,
        v_mps=v_r / 3.6,
        a_long_mps2=alon_smooth,
        a_lat_mps2=alat_smooth,
        yaw_rate_rads=yaw_r,
        accel_pedal_pct=aped_r,
        brake_pressed=(bped_r >= 2).astype(float),
        v_ovrgnd_mps=v_og_r / 3.6,
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("usage: python adapter_ford_rlog.py <path/to/rlog.zst>")
        sys.exit(2)
    from parameters import MACH_E
    m = load_segment_measurements(Path(sys.argv[1]), steer_ratio=MACH_E.i_s)
    print(f"N={len(m.t)}  duration={m.t[-1]:.1f} s")
    print(f"  v       ∈ [{m.v_mps.min():.1f}, {m.v_mps.max():.1f}] m/s")
    print(f"  δ_wheel ∈ [{m.delta_wheel_deg.min():.1f}, {m.delta_wheel_deg.max():.1f}] deg")
    print(f"  yaw     ∈ [{np.degrees(m.yaw_rate_rads).min():.1f}, "
          f"{np.degrees(m.yaw_rate_rads).max():.1f}] deg/s")
    print(f"  a_long  ∈ [{m.a_long_mps2.min():.2f}, {m.a_long_mps2.max():.2f}] m/s²")
    print(f"  a_lat   ∈ [{m.a_lat_mps2.min():.2f}, {m.a_lat_mps2.max():.2f}] m/s²")
