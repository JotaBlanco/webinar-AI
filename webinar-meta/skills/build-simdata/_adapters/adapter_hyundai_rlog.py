"""Hyundai E-GMP rlog → KS driver inputs adapter (real data path).

Reads decoded CAN-FD frames out of a commaCarSegments Hyundai Ioniq 5 rlog
(or any other E-GMP platform that shares hyundai_canfd.dbc) and produces:

  - KSDriverInputs               — (t, delta_dot, a, delta_meas) at 50 Hz
  - HyundaiRealMeasurements      — the rest of the decoded signals, INCLUDING
                                   the IMU-grade yaw rate from
                                   `IMU_01_10ms.IMU_YawRtVal` (deg/s) and the
                                   lateral acceleration from
                                   `IMU_01_10ms.IMU_LatAccelVal` (g).

Provenance reality check (from probing the rlogs themselves):

  - Same envelope as the Tesla/Ford rlogs: only `can`, `pandaStates`,
    `carParams`. The comma3 was logging passively from the bus; controlsd/
    locationd were not running. Every signal comes from decoded CAN.
  - E-GMP uses CAN-FD on bus 1 (primary traction-CAN). Buses 0 and 2 carry
    different subnets (chassis, ADAS). The panda mirrors bus 1 onto bus 129,
    we ignore that.
  - The CAN-FD DBC is built by concatenating two opendbc generator fragments;
    see [_schema/dbc/COMMIT.txt]. Must be loaded with `strict=False` because
    SCC_CONTROL contains intentional overlapping signals.

What we have, end-to-end (Ioniq 5, same DBC works for Ioniq 6 / EV6 / Niro
EV / Kona EV / other E-GMP platforms):

  Address  Bus  Message              Signal                 Units  Role
  -------  ---  -------------------  ---------------------  -----  ------
   0x04A   1    IMU_01_10ms          IMU_YawRtVal           deg/s  TRUTH  (yaw rate)
   0x04A   1    IMU_01_10ms          IMU_LatAccelVal        g      TRUTH  (a_y)
   0x0A0   1    WHEEL_SPEEDS         WHL_SpdFLVal           kph    INPUT  (speed, FL)
   0x0A0   1    WHEEL_SPEEDS         WHL_SpdFRVal           kph    extra
   0x0A0   1    WHEEL_SPEEDS         WHL_SpdRLVal           kph    extra
   0x0A0   1    WHEEL_SPEEDS         WHL_SpdRRVal           kph    extra
   0x125   1    STEERING_SENSORS     STEERING_ANGLE         deg    INPUT  (wheel angle)
   0x125   1    STEERING_SENSORS     STEERING_RATE          deg/s  extra
   0x035   1    ACCELERATOR          ACCELERATOR_PEDAL      raw    extra
   0x065   1    BRAKE                (decoded structure)    raw    extra

Speed is computed as the mean of the four wheel speeds. Longitudinal
acceleration is not directly broadcast in E-GMP DBC at a useful rate, so
a_long is derived numerically from d(v)/dt with a 5 Hz low-pass (same
strategy as the Tesla adapter).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from rlog_reader import iter_events

_HERE = Path(__file__).resolve().parent
DEFAULT_DBC = _HERE.parent / "_schema" / "dbc" / "hyundai_canfd.dbc"

# Hyundai E-GMP CAN-FD addresses we read.
ADDR_IMU    = 0x04A    # IMU_01_10ms          (yaw rate + lat-accel)
ADDR_WHEELS = 0x0A0    # WHEEL_SPEEDS         (FL/FR/RL/RR)
ADDR_STEER  = 0x125    # STEERING_SENSORS     (angle + rate)

# E-GMP primary traction CAN-FD is bus 1 on some panda units and bus 5 on
# others (the panda relabels buses depending on hardware revision / harness).
# Mirrors live at +128 (e.g. bus 1 → 129, bus 5 → 133). We accept every
# non-mirror bus and let the wanted-address filter sort it out — the target
# addresses (0x04A, 0x0A0, 0x125) only broadcast on the real traction bus,
# never twice.
def _is_real_bus(src: int) -> bool:
    return src < 128


@dataclass
class HyundaiRealMeasurements:
    """Decoded + resampled signals from one Hyundai rlog, uniform 50 Hz grid."""
    t: np.ndarray                       # [s], shape (N,)
    delta_wheel_deg: np.ndarray         # steering wheel angle [deg]
    delta_road_rad: np.ndarray          # steering wheel / steerRatio [rad]
    v_mps: np.ndarray                   # vehicle speed [m/s]  (mean of 4 wheels)
    a_long_mps2: np.ndarray             # numerical d(v)/dt, 5 Hz LP [m/s²]
    a_lat_mps2: np.ndarray              # measured lateral acc [m/s²]    ← TRUTH
    yaw_rate_rads: np.ndarray           # measured yaw rate [rad/s]      ← TRUTH
    steer_rate_dps: np.ndarray          # steering rate [deg/s]
    v_fl_mps: np.ndarray                # individual wheel speeds [m/s]
    v_fr_mps: np.ndarray
    v_rl_mps: np.ndarray
    v_rr_mps: np.ndarray


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
            if _is_real_bus(fr.src) and fr.address in want:
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


# Conversions
DEG_TO_RAD = np.pi / 180.0
G_TO_MPS2  = 9.80665


def load_segment_measurements(
    rlog_path: Path,
    steer_ratio: float,
    sample_rate_hz: float = 50.0,
    dbc_path: Path | None = None,
    crop_edges_s: float = 1.0,
) -> HyundaiRealMeasurements:
    """Decode one Hyundai E-GMP rlog into a uniform-rate measurement dataframe.

    `steer_ratio` is taken from the platform's parameter set
    (parameters.IONIQ_5.i_s) rather than hard-coded.
    """
    import cantools

    db = cantools.database.load_file(str(dbc_path or DEFAULT_DBC), strict=False)

    addrs = (ADDR_IMU, ADDR_WHEELS, ADDR_STEER)
    records = {a: [] for a in addrs}
    for t_ns, addr, dat in _frame_iter(Path(rlog_path), addrs):
        records[addr].append((t_ns, dat))

    t_iy, yaw_dps      = _decode_series(records, ADDR_IMU,    "IMU_YawRtVal",     db)
    t_ia, lat_g        = _decode_series(records, ADDR_IMU,    "IMU_LatAccelVal",  db)
    t_fl, v_fl_kph     = _decode_series(records, ADDR_WHEELS, "WHL_SpdFLVal",     db)
    t_fr, v_fr_kph     = _decode_series(records, ADDR_WHEELS, "WHL_SpdFRVal",     db)
    t_rl, v_rl_kph     = _decode_series(records, ADDR_WHEELS, "WHL_SpdRLVal",     db)
    t_rr, v_rr_kph     = _decode_series(records, ADDR_WHEELS, "WHL_SpdRRVal",     db)
    t_st, steer_deg    = _decode_series(records, ADDR_STEER,  "STEERING_ANGLE",   db)
    t_sr, steer_rate   = _decode_series(records, ADDR_STEER,  "STEERING_RATE",    db)

    if len(steer_deg) < 100 or len(v_fl_kph) < 50 or len(yaw_dps) < 100:
        raise RuntimeError(
            f"Segment {rlog_path} decoded too few frames: "
            f"steer={len(steer_deg)} wheels={len(v_fl_kph)} yaw={len(yaw_dps)}. "
            "Likely partial rlog or wrong DBC bus."
        )

    t_start = max(t_iy.min(), t_ia.min(), t_fl.min(), t_fr.min(),
                  t_rl.min(), t_rr.min(), t_st.min(), t_sr.min()) + crop_edges_s
    t_end   = min(t_iy.max(), t_ia.max(), t_fl.max(), t_fr.max(),
                  t_rl.max(), t_rr.max(), t_st.max(), t_sr.max()) - crop_edges_s
    if t_end - t_start < 5.0:
        raise RuntimeError(f"Segment {rlog_path} too short after edge crop")

    dt = 1.0 / sample_rate_hz
    t_grid = np.arange(t_start, t_end, dt)

    yaw_r       = _resample(t_grid, t_iy, yaw_dps) * DEG_TO_RAD
    lat_r       = _resample(t_grid, t_ia, lat_g)   * G_TO_MPS2
    v_fl_r      = _resample(t_grid, t_fl, v_fl_kph) / 3.6
    v_fr_r      = _resample(t_grid, t_fr, v_fr_kph) / 3.6
    v_rl_r      = _resample(t_grid, t_rl, v_rl_kph) / 3.6
    v_rr_r      = _resample(t_grid, t_rr, v_rr_kph) / 3.6
    steer_r     = _resample(t_grid, t_st, steer_deg)
    steer_rt_r  = _resample(t_grid, t_sr, steer_rate)

    v_r = 0.25 * (v_fl_r + v_fr_r + v_rl_r + v_rr_r)

    # a_long not directly broadcast; derive numerically with light low-pass
    a_long = np.gradient(v_r, dt)
    a_long_smooth = _lowpass(a_long, sample_rate_hz, cutoff_hz=5.0)

    # Light low-pass on the lateral channel (same reasoning as Ford adapter)
    lat_smooth = _lowpass(lat_r, sample_rate_hz, cutoff_hz=5.0)

    delta_road = np.deg2rad(steer_r) / steer_ratio

    return HyundaiRealMeasurements(
        t=t_grid - t_grid[0],
        delta_wheel_deg=steer_r,
        delta_road_rad=delta_road,
        v_mps=v_r,
        a_long_mps2=a_long_smooth,
        a_lat_mps2=lat_smooth,
        yaw_rate_rads=yaw_r,
        steer_rate_dps=steer_rt_r,
        v_fl_mps=v_fl_r,
        v_fr_mps=v_fr_r,
        v_rl_mps=v_rl_r,
        v_rr_mps=v_rr_r,
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("usage: python adapter_hyundai_rlog.py <path/to/rlog.zst>")
        sys.exit(2)
    from parameters import IONIQ_5
    m = load_segment_measurements(Path(sys.argv[1]), steer_ratio=IONIQ_5.i_s)
    print(f"N={len(m.t)}  duration={m.t[-1]:.1f} s")
    print(f"  v       ∈ [{m.v_mps.min():.1f}, {m.v_mps.max():.1f}] m/s")
    print(f"  δ_wheel ∈ [{m.delta_wheel_deg.min():.1f}, {m.delta_wheel_deg.max():.1f}] deg")
    print(f"  yaw     ∈ [{np.degrees(m.yaw_rate_rads).min():.1f}, "
          f"{np.degrees(m.yaw_rate_rads).max():.1f}] deg/s")
    print(f"  a_lat   ∈ [{m.a_lat_mps2.min():.2f}, {m.a_lat_mps2.max():.2f}] m/s²")
    print(f"  a_long  ∈ [{m.a_long_mps2.min():.2f}, {m.a_long_mps2.max():.2f}] m/s² (derived)")
