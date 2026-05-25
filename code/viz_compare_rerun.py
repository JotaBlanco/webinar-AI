"""Option C — rerun.io sim-vs-real overlay with cinematic 3D scene.

Loads a sim.csv (Tesla Model 3, Ford F-150 Lightning, or Ford Mustang Mach-E),
auto-detects which channels are present, and logs to rerun:

3D scene:
- /world/car           procedural car silhouette at the model-integrated pose
- /world/real_pose     red sphere at the measured pose (integrated from
                       measured yaw rate when available; wheel-speed Ackermann
                       on Tesla as a fallback proxy)
- /world/ground/sim_path   model trajectory (blue)
- /world/ground/real_path  measured trajectory (red)
- /world/ground/grid       100x100 m ground grid
- /world/chase_cam     a Pinhole whose Transform3D updates per frame; the
                       main 3D view's eye locks onto it via EyeControls3D

Six time-series plots, two real-vs-sim each where data permits, arranged in
a 2x2 grid with the 3D view in the top-right quadrant:
    speed | steering         3D chase view
    yaw   | lat G            yaw resid | lat-G resid

Tesla schema lacks measured yaw rate and lateral G (no IMU in those rlogs)
— the "real" yaw rate is reconstructed from wheel-speed Ackermann and the
real lateral G panel falls back to sim-only.
Ford schemas include both directly from the CAN bus (Yaw_Data_FD1,
BrakeSnData_3) — the comparison is honest end-to-end.

CLI:
    python viz_compare_rerun.py --list                  # show all segments
    python viz_compare_rerun.py                          # default: first Ford F-150
    python viz_compare_rerun.py --segment 5              # segment index from --list
    python viz_compare_rerun.py --segment 0 --spawn      # open viewer directly
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import rerun as rr
import rerun.blueprint as rrb
from rerun.blueprint.components import Eye3DKind

KB003 = Path(__file__).resolve().parents[1]
SIMDATA_ROOT = KB003 / "data" / "sim"
OUT_ROOT = Path(__file__).parent / "out/sim_vs_real"

# Platform → approximate published dimensions (m) + a body colour. Used to
# scale the procedural mesh so a pickup looks like a pickup and a sedan like
# a sedan in the 3D view. Track is the rear track width and is also the
# divisor in the Tesla wheel-speed Ackermann fallback.
CAR_DIMS: dict[str, dict] = {
    "TESLA_MODEL_3": {
        "L": 4.694, "W": 1.849, "H": 1.443, "WB": 2.875, "track": 1.580,
        "color": (200, 30, 30),         # Red Multi-Coat
    },
    "FORD_F_150_LIGHTNING_MK1": {
        "L": 5.910, "W": 2.029, "H": 1.999, "WB": 3.706, "track": 1.730,
        "color": (220, 220, 230),       # Iconic Silver
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "L": 4.713, "W": 1.881, "H": 1.621, "WB": 2.984, "track": 1.620,
        "color": (40, 70, 170),         # Grabber Blue-ish
    },
}

WHEEL_RADIUS = 0.350
WHEEL_WIDTH = 0.220

# Plot colours.
SIM_LINE = (214, 39, 40)         # red
REAL_LINE = (10, 10, 10)         # black
RESID_LINE = (148, 103, 189)     # purple

# 3D ornament colours.
ROOF_GLASS = (40, 40, 50, 200)
WHEEL_COLOR = (20, 20, 20)
HEADLIGHT = (255, 240, 200)
TAILLIGHT = (180, 30, 30)
GRID_COLOR = (90, 90, 100)
TRAJ_COLOR = (31, 119, 180)
REAL_COLOR = (214, 39, 40)


# --- segment discovery ----------------------------------------------------


@dataclass
class Segment:
    platform: str
    device: str
    route: str
    idx: str
    csv_path: Path

    @property
    def slug(self) -> str:
        return f"{self.platform}__{self.device[:8]}__{self.route.split('--')[-1][:8]}__{self.idx}"


def discover_segments() -> list[Segment]:
    """Scan every manifest.json under data/sim/segments and return all segments."""
    out: list[Segment] = []
    for manifest_path in sorted(SIMDATA_ROOT.glob("segments/*/manifest.json")):
        m = json.loads(manifest_path.read_text())
        for seg in m["segments"]:
            out.append(Segment(
                platform=m["platform"],
                device=seg["device"],
                route=seg["route"],
                idx=str(seg["idx"]),
                csv_path=SIMDATA_ROOT / seg["csv_path"],
            ))
    return out


# --- schema resolution ----------------------------------------------------


@dataclass
class Schema:
    """Column-name resolution + capability flags for one CSV."""
    yaw_sim_col: str            # "yaw_rate_pred_rads" (Ford) or "psi_dot_rads" (Tesla)
    a_y_sim_col: str            # "a_y_pred_mps2" (Ford) or "a_y_mps2" (Tesla)
    yaw_real_col: str | None    # "yaw_rate_meas_rads" (Ford); None on Tesla
    a_y_real_col: str | None    # "a_lat_meas_mps2" (Ford); None on Tesla
    yaw_resid_col: str | None   # "yaw_rate_resid_rads" (Ford); computed on Tesla
    a_y_resid_col: str | None   # "a_y_resid_mps2" (Ford); None on Tesla
    has_wheel_speeds: bool      # Tesla: wheel_FL/FR/RL/RR_kph for Ackermann


def resolve_schema(df: pd.DataFrame) -> Schema:
    cols = set(df.columns)
    return Schema(
        yaw_sim_col="yaw_rate_pred_rads" if "yaw_rate_pred_rads" in cols else "psi_dot_rads",
        a_y_sim_col="a_y_pred_mps2" if "a_y_pred_mps2" in cols else "a_y_mps2",
        yaw_real_col="yaw_rate_meas_rads" if "yaw_rate_meas_rads" in cols else None,
        a_y_real_col="a_lat_meas_mps2" if "a_lat_meas_mps2" in cols else None,
        yaw_resid_col="yaw_rate_resid_rads" if "yaw_rate_resid_rads" in cols else None,
        a_y_resid_col="a_y_resid_mps2" if "a_y_resid_mps2" in cols else None,
        has_wheel_speeds="wheel_RR_kph" in cols and "wheel_RL_kph" in cols,
    )


# --- procedural mesh ------------------------------------------------------


def cylinder_mesh(radius: float, length: float, axis: str = "y",
                  segments: int = 24) -> tuple[np.ndarray, np.ndarray]:
    """Vertices + triangle indices for a closed cylinder centred at origin."""
    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    ring0 = np.column_stack([radius * np.cos(angles),
                             np.full_like(angles, -length / 2),
                             radius * np.sin(angles)])
    ring1 = np.column_stack([radius * np.cos(angles),
                             np.full_like(angles, length / 2),
                             radius * np.sin(angles)])
    centers = np.array([[0, -length / 2, 0], [0, length / 2, 0]])
    if axis == "x":
        rot = np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]])
        ring0, ring1, centers = ring0 @ rot.T, ring1 @ rot.T, centers @ rot.T
    elif axis == "z":
        rot = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])
        ring0, ring1, centers = ring0 @ rot.T, ring1 @ rot.T, centers @ rot.T

    verts = np.vstack([ring0, ring1, centers])
    n = segments
    side_tris = []
    for i in range(n):
        j = (i + 1) % n
        side_tris.append([i, j, n + j])
        side_tris.append([i, n + j, n + i])
    cap0 = [[2 * n, (i + 1) % n, i] for i in range(n)]
    cap1 = [[2 * n + 1, n + i, n + ((i + 1) % n)] for i in range(n)]
    tris = np.array(side_tris + cap0 + cap1)
    return verts.astype(np.float32), tris.astype(np.uint32)


def log_car_static(dims: dict) -> None:
    """Log the procedural silhouette under /world/car for a given platform."""
    L, W, H, WB, track = dims["L"], dims["W"], dims["H"], dims["WB"], dims["track"]
    body = dims["color"]

    # Lower + mid body — two stacked boxes, body colour.
    rr.log("/world/car/body_lower",
           rr.Boxes3D(centers=[[0, 0, WHEEL_RADIUS + 0.25]],
                      half_sizes=[[L / 2 * 0.96, W / 2, 0.25]],
                      colors=[body], fill_mode="solid"),
           static=True)
    rr.log("/world/car/body_mid",
           rr.Boxes3D(centers=[[0, 0, WHEEL_RADIUS + 0.55]],
                      half_sizes=[[L / 2 * 0.92, W / 2 * 0.94, 0.20]],
                      colors=[body], fill_mode="solid"),
           static=True)
    # Cabin — narrower, taller, dark glass.
    cabin_z_top = WHEEL_RADIUS + max(0.95, H - 0.5)
    rr.log("/world/car/cabin",
           rr.Boxes3D(centers=[[-0.10, 0, cabin_z_top]],
                      half_sizes=[[L / 2 * 0.42, W / 2 * 0.82, 0.20]],
                      colors=[ROOF_GLASS], fill_mode="solid"),
           static=True)

    # Wheels — four cylinders at WB/2 ahead/behind and track/2 left/right.
    verts, tris = cylinder_mesh(WHEEL_RADIUS, WHEEL_WIDTH, axis="y")
    wheel_centers = [
        ( WB / 2,  track / 2, WHEEL_RADIUS),
        ( WB / 2, -track / 2, WHEEL_RADIUS),
        (-WB / 2,  track / 2, WHEEL_RADIUS),
        (-WB / 2, -track / 2, WHEEL_RADIUS),
    ]
    for name, c in zip(["fl", "fr", "rl", "rr"], wheel_centers):
        rr.log(f"/world/car/wheel_{name}",
               rr.Mesh3D(vertex_positions=verts + np.array(c, dtype=np.float32),
                         triangle_indices=tris,
                         vertex_colors=np.tile(np.array(WHEEL_COLOR, dtype=np.uint8),
                                               (len(verts), 1))),
               static=True)

    # Lights.
    rr.log("/world/car/headlights",
           rr.Boxes3D(centers=[[L / 2 * 0.96,  W / 2 * 0.75, WHEEL_RADIUS + 0.45],
                                [L / 2 * 0.96, -W / 2 * 0.75, WHEEL_RADIUS + 0.45]],
                      half_sizes=[[0.05, 0.18, 0.06]] * 2,
                      colors=[HEADLIGHT] * 2, fill_mode="solid"),
           static=True)
    rr.log("/world/car/taillights",
           rr.Boxes3D(centers=[[-L / 2 * 0.96,  W / 2 * 0.75, WHEEL_RADIUS + 0.55],
                                [-L / 2 * 0.96, -W / 2 * 0.75, WHEEL_RADIUS + 0.55]],
                      half_sizes=[[0.05, 0.20, 0.05]] * 2,
                      colors=[TAILLIGHT] * 2, fill_mode="solid"),
           static=True)


# --- measured trajectory --------------------------------------------------


def compute_real_trajectory(df: pd.DataFrame, schema: Schema, track: float) -> np.ndarray:
    """Reconstruct measured (x, y, psi) at 50 Hz.

    Priority:
    1. yaw_rate_meas_rads from the CAN bus (Ford) — preferred, no model
       assumptions beyond integration drift.
    2. Wheel-speed Ackermann (Tesla fallback) — (v_RL - v_RR) / track,
       sign-flipped to match the model's psi convention; ignores tyre slip.

    Forward speed is v_mps in both cases.

    Returns an (N, 3) array of (x, y, psi).
    """
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0] - (t[1] - t[0]))
    v_meas = df["v_mps"].to_numpy()

    if schema.yaw_real_col is not None:
        psi_dot = df[schema.yaw_real_col].to_numpy()
    elif schema.has_wheel_speeds:
        v_RR = df["wheel_RR_kph"].to_numpy() / 3.6
        v_RL = df["wheel_RL_kph"].to_numpy() / 3.6
        # Sign-flipped — see prior debugging note. The Tesla CAN labels for
        # ESP_wheelSpeedReL/ReR appear inverted relative to the model's
        # steering-angle convention; this flip makes them share a frame.
        psi_dot = (v_RL - v_RR) / track
    else:
        # Should never happen for the platforms we ship — guard regardless.
        psi_dot = np.zeros_like(t)

    psi = np.cumsum(psi_dot * dt)
    x = np.cumsum(v_meas * np.cos(psi) * dt)
    y = np.cumsum(v_meas * np.sin(psi) * dt)
    return np.column_stack([x, y, psi])


# --- ground + path overlay ------------------------------------------------


def log_ground_and_paths(sim_xy: np.ndarray, real_xyp: np.ndarray) -> None:
    xs = np.concatenate([sim_xy[:, 0], real_xyp[:, 0]])
    ys = np.concatenate([sim_xy[:, 1], real_xyp[:, 1]])
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    half = max(np.ptp(xs), np.ptp(ys), 200) / 2 + 50
    spacing = 10.0

    grid_lines = []
    n = int(half // spacing) + 1
    for i in range(-n, n + 1):
        x = cx + i * spacing
        grid_lines.append([[x, cy - half, 0], [x, cy + half, 0]])
    for j in range(-n, n + 1):
        y = cy + j * spacing
        grid_lines.append([[cx - half, y, 0], [cx + half, y, 0]])
    rr.log("/world/ground/grid",
           rr.LineStrips3D(grid_lines, colors=[GRID_COLOR], radii=0.03),
           static=True)

    sim_z = np.column_stack([sim_xy[:, 0], sim_xy[:, 1], np.full(len(sim_xy), 0.02)])
    rr.log("/world/ground/sim_path",
           rr.LineStrips3D([sim_z], colors=[TRAJ_COLOR], radii=0.25),
           static=True)
    real_z = np.column_stack([real_xyp[:, 0], real_xyp[:, 1], np.full(len(real_xyp), 0.03)])
    rr.log("/world/ground/real_path",
           rr.LineStrips3D([real_z], colors=[REAL_COLOR], radii=0.25),
           static=True)
    rr.log("/world/ground/start",
           rr.Points3D([[sim_xy[0, 0], sim_xy[0, 1], 0.1]],
                       colors=[(0, 220, 0)], radii=0.8, labels=["start"]),
           static=True)
    rr.log("/world/ground/end_sim",
           rr.Points3D([[sim_xy[-1, 0], sim_xy[-1, 1], 0.1]],
                       colors=[TRAJ_COLOR], radii=0.6, labels=["sim end"]),
           static=True)
    rr.log("/world/ground/end_real",
           rr.Points3D([[real_xyp[-1, 0], real_xyp[-1, 1], 0.1]],
                       colors=[REAL_COLOR], radii=0.6, labels=["real end"]),
           static=True)


# --- chase camera ---------------------------------------------------------


def chase_cam_pose(x: float, y: float, psi: float,
                   back: float, up: float) -> tuple[np.ndarray, np.ndarray]:
    """Camera pose `back` m behind the car (in heading direction), `up` m above ground."""
    fwd_xy = np.array([math.cos(psi), math.sin(psi)])
    cam_pos = np.array([x - back * fwd_xy[0], y - back * fwd_xy[1], up])
    target = np.array([x + 2.0 * fwd_xy[0], y + 2.0 * fwd_xy[1], WHEEL_RADIUS + 0.6])
    forward = target - cam_pos
    forward /= np.linalg.norm(forward)
    world_up = np.array([0.0, 0.0, 1.0])
    right = np.cross(forward, world_up); right /= np.linalg.norm(right)
    down = np.cross(forward, right); down /= np.linalg.norm(down)
    mat = np.column_stack([right, down, forward]).astype(np.float32)
    return cam_pos.astype(np.float32), mat


# --- main logging ---------------------------------------------------------


def log_dataset(df: pd.DataFrame, schema: Schema, dims: dict) -> None:
    sim_xy = np.column_stack([df["x_m"].to_numpy(), df["y_m"].to_numpy()])
    real_xyp = compute_real_trajectory(df, schema, dims["track"])

    log_ground_and_paths(sim_xy, real_xyp)
    log_car_static(dims)

    rr.log("/world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
    rr.log("/world/chase_cam",
           rr.Pinhole(focal_length=600, width=1280, height=720),
           static=True)

    # Per-channel style — sim=red, real=black, residual=purple, all overlapped
    # in the same plot panel per channel.
    def style(path: str, color, name: str, width: float = 1.6) -> None:
        rr.log(path, rr.SeriesLines(colors=[color], names=[name], widths=[width]),
               static=True)

    style("/plots/speed/sim", SIM_LINE, "sim", 2.0)
    style("/plots/speed/real", REAL_LINE, "real", 1.4)
    style("/plots/steer/sim", SIM_LINE, "sim", 2.0)
    style("/plots/steer/real", REAL_LINE, "real", 1.4)
    style("/plots/yaw_rate/sim", SIM_LINE, "sim", 2.0)
    if schema.yaw_real_col or schema.has_wheel_speeds:
        style("/plots/yaw_rate/real", REAL_LINE,
              "real" if schema.yaw_real_col else "real (wheel-speed proxy)", 1.4)
    style("/plots/a_y/sim", SIM_LINE, "sim", 2.0)
    if schema.a_y_real_col:
        style("/plots/a_y/real", REAL_LINE, "real", 1.4)
    style("/plots/yaw_resid", RESID_LINE, "sim - real", 1.6)
    style("/plots/a_y_resid", RESID_LINE, "sim - real", 1.6)

    t = df["t_s"].to_numpy()

    for i in range(len(df)):
        rr.set_time("sim_time", duration=float(t[i]))

        # Sim pose drives the full car mesh at /world/car.
        psi = float(df["psi_rad"].iat[i])
        x = float(df["x_m"].iat[i])
        y = float(df["y_m"].iat[i])
        rr.log("/world/car",
               rr.Transform3D(translation=[x, y, 0.0],
                              rotation=rr.RotationAxisAngle(
                                  axis=[0.0, 0.0, 1.0],
                                  angle=rr.Angle(rad=psi))))

        # Chase camera follows.
        cam_pos, cam_mat = chase_cam_pose(x, y, psi, back=10.0, up=4.0)
        rr.log("/world/chase_cam",
               rr.Transform3D(translation=cam_pos.tolist(),
                              mat3x3=cam_mat.tolist()))

        # Measured pose ghost.
        rx, ry = float(real_xyp[i, 0]), float(real_xyp[i, 1])
        rr.log("/world/real_pose",
               rr.Points3D([[rx, ry, WHEEL_RADIUS + 0.7]],
                           colors=[REAL_COLOR], radii=0.6, labels=["real"]))

        # Scalar channels.
        rr.log("/plots/speed/real", rr.Scalars(float(df["v_mps"].iat[i])))
        rr.log("/plots/speed/sim", rr.Scalars(float(df["v_state_mps"].iat[i])))
        rr.log("/plots/steer/real", rr.Scalars(float(df["delta_road_rad"].iat[i])))
        rr.log("/plots/steer/sim", rr.Scalars(float(df["delta_state_rad"].iat[i])))
        rr.log("/plots/yaw_rate/sim", rr.Scalars(float(df[schema.yaw_sim_col].iat[i])))
        rr.log("/plots/a_y/sim", rr.Scalars(float(df[schema.a_y_sim_col].iat[i])))

        if schema.yaw_real_col:
            rr.log("/plots/yaw_rate/real", rr.Scalars(float(df[schema.yaw_real_col].iat[i])))
        elif schema.has_wheel_speeds:
            # log the wheel-speed-derived psi_dot used for the real path
            v_RR = float(df["wheel_RR_kph"].iat[i]) / 3.6
            v_RL = float(df["wheel_RL_kph"].iat[i]) / 3.6
            rr.log("/plots/yaw_rate/real",
                   rr.Scalars((v_RL - v_RR) / dims["track"]))

        if schema.a_y_real_col:
            rr.log("/plots/a_y/real", rr.Scalars(float(df[schema.a_y_real_col].iat[i])))

        if schema.yaw_resid_col:
            rr.log("/plots/yaw_resid", rr.Scalars(float(df[schema.yaw_resid_col].iat[i])))
        elif schema.yaw_real_col or schema.has_wheel_speeds:
            # Compute on the fly: sim - real
            sim_v = float(df[schema.yaw_sim_col].iat[i])
            if schema.yaw_real_col:
                real_v = float(df[schema.yaw_real_col].iat[i])
            else:
                v_RR = float(df["wheel_RR_kph"].iat[i]) / 3.6
                v_RL = float(df["wheel_RL_kph"].iat[i]) / 3.6
                real_v = (v_RL - v_RR) / dims["track"]
            rr.log("/plots/yaw_resid", rr.Scalars(sim_v - real_v))

        if schema.a_y_resid_col:
            rr.log("/plots/a_y_resid", rr.Scalars(float(df[schema.a_y_resid_col].iat[i])))
        elif schema.a_y_real_col:
            rr.log("/plots/a_y_resid",
                   rr.Scalars(float(df[schema.a_y_sim_col].iat[i]) -
                              float(df[schema.a_y_real_col].iat[i])))


def default_blueprint(segment: Segment) -> rrb.Blueprint:
    """2x2 layout: 3D chase view top-right, 6 plots in the other quadrants.

      ┌─────────────────────┬──────────────────────┐
      │  speed  │  steer    │                      │
      ├─────────┴───────────┤   3D chase view      │
      │  yaw    │  lat G    │   (top-right)        │
      ├─────────┴───────────┤                      │
      │  yaw rs │  a_y res  │                      │
      └─────────────────────┴──────────────────────┘
    """
    chase = rrb.EyeControls3D(
        kind=Eye3DKind.FirstPerson,
        tracking_entity="/world/chase_cam",
    )
    return rrb.Blueprint(
        rrb.Horizontal(
            rrb.Vertical(
                rrb.Horizontal(
                    rrb.TimeSeriesView(origin="/plots/speed", name="Speed (m/s)"),
                    rrb.TimeSeriesView(origin="/plots/steer", name="Steering (rad)"),
                ),
                rrb.Horizontal(
                    rrb.TimeSeriesView(origin="/plots/yaw_rate", name="Yaw rate (rad/s)"),
                    rrb.TimeSeriesView(origin="/plots/a_y", name="Lateral G (m/s²)"),
                ),
                rrb.Horizontal(
                    rrb.TimeSeriesView(origin="/plots/yaw_resid", name="Yaw rate residual"),
                    rrb.TimeSeriesView(origin="/plots/a_y_resid", name="Lat G residual"),
                ),
            ),
            rrb.Spatial3DView(
                origin="/world",
                name=f"Chase view — {segment.platform}",
                eye_controls=chase,
            ),
            column_shares=[1, 1],
        ),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--list", action="store_true",
                    help="print all available segments and exit")
    ap.add_argument("--segment", type=int, default=0,
                    help="segment index from --list (default: 0 — first segment)")
    ap.add_argument("--spawn", action="store_true",
                    help="open the native rerun viewer instead of saving an .rrd")
    args = ap.parse_args()

    segments = discover_segments()
    if not segments:
        raise SystemExit(f"No segments found under {SIMDATA_ROOT}.")

    if args.list:
        print(f"{'idx':>4}  {'platform':32s}  device / route / segment")
        for i, s in enumerate(segments):
            print(f"  {i:2d}   {s.platform:32s}  {s.device[:12]} / {s.route[:14]} / {s.idx}")
        return

    if args.segment < 0 or args.segment >= len(segments):
        raise SystemExit(f"--segment must be in [0, {len(segments)}). Use --list.")

    seg = segments[args.segment]
    if seg.platform not in CAR_DIMS:
        raise SystemExit(f"No CAR_DIMS entry for platform {seg.platform!r}.")
    dims = CAR_DIMS[seg.platform]

    df = pd.read_csv(seg.csv_path)
    schema = resolve_schema(df)

    out_dir = OUT_ROOT / seg.slug
    out_dir.mkdir(parents=True, exist_ok=True)

    # App id bumped per blueprint change so the viewer doesn't cache a stale
    # layout. Suffix with the platform so each car gets its own slot too.
    rr.init(f"sim_vs_real_v6_{seg.platform.lower()}", spawn=args.spawn)
    if not args.spawn:
        rr.save(str(out_dir / "compare.rrd"))

    rr.send_blueprint(default_blueprint(seg), make_active=True, make_default=True)

    print(f"segment:   [{args.segment}] {seg.platform}  {seg.device[:12]} / {seg.route[:14]} / {seg.idx}")
    print(f"schema:    yaw_sim={schema.yaw_sim_col}  yaw_real={schema.yaw_real_col}  "
          f"a_y_real={schema.a_y_real_col}  wheel_speeds={schema.has_wheel_speeds}")

    log_dataset(df, schema, dims)

    if not args.spawn:
        out_path = out_dir / "compare.rrd"
        print(f"wrote {out_path}")
        print(f"open with:  rerun {out_path.relative_to(KB003.parent)}")


if __name__ == "__main__":
    main()
