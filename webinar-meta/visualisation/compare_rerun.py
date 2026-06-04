"""Rerun N-agent 3D scene.

3D layout
- /world/car_baseline       procedural V0 car mesh (camera tracks this)
- /world/ground/path_<run>  one line strip per run (measured, V0, agent_*)
- /world/pose_<run>          a coloured ball per run at the current pose
- /world/chase_cam           pinhole rig tracked by the 3D view

Plot layout (overlaid per-run)
- /plots/yaw_rate/<run>      yaw rate (every run)
- /plots/yaw_resid/<run>     yaw rate residual (every non-truth run)
- /plots/xy_err/<run>        XY error vs measured truth (every non-truth run)
- /plots/inputs/v            measured speed
- /plots/inputs/delta         steering input

Run with --spawn to launch the viewer directly; otherwise an .rrd file is
written under out/<seg_slug>/compare.rrd.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import rerun as rr
import rerun.blueprint as rrb
from rerun.blueprint.components import Eye3DKind

from _runner import CAR_DIMS, RunResult, Schema, Segment

OUT_ROOT = Path(__file__).resolve().parent / "out"

WHEEL_RADIUS = 0.350
WHEEL_WIDTH = 0.220
ROOF_GLASS = (40, 40, 50, 200)
WHEEL_COLOR = (20, 20, 20)
HEADLIGHT = (255, 240, 200)
TAILLIGHT = (180, 30, 30)
GRID_COLOR = (90, 90, 100)


# --- procedural car mesh (kept compact — one stack of boxes + 4 wheels) ----


def _cyl(radius: float, length: float, axis: str = "y",
         segments: int = 24) -> tuple[np.ndarray, np.ndarray]:
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
    side = [[i, (i + 1) % n, n + ((i + 1) % n)] for i in range(n)] + \
           [[i, n + ((i + 1) % n), n + i] for i in range(n)]
    cap0 = [[2 * n, (i + 1) % n, i] for i in range(n)]
    cap1 = [[2 * n + 1, n + i, n + ((i + 1) % n)] for i in range(n)]
    tris = np.array(side + cap0 + cap1)
    return verts.astype(np.float32), tris.astype(np.uint32)


def _log_car_static(dims: dict) -> None:
    L, W, H, WB, track = dims["L"], dims["W"], dims["H"], dims["WB"], dims["track"]
    body = dims["color"]
    rr.log("/world/car_baseline/body_lower",
           rr.Boxes3D(centers=[[0, 0, WHEEL_RADIUS + 0.25]],
                      half_sizes=[[L / 2 * 0.96, W / 2, 0.25]],
                      colors=[body], fill_mode="solid"), static=True)
    rr.log("/world/car_baseline/body_mid",
           rr.Boxes3D(centers=[[0, 0, WHEEL_RADIUS + 0.55]],
                      half_sizes=[[L / 2 * 0.92, W / 2 * 0.94, 0.20]],
                      colors=[body], fill_mode="solid"), static=True)
    cabin_z_top = WHEEL_RADIUS + max(0.95, H - 0.5)
    rr.log("/world/car_baseline/cabin",
           rr.Boxes3D(centers=[[-0.10, 0, cabin_z_top]],
                      half_sizes=[[L / 2 * 0.42, W / 2 * 0.82, 0.20]],
                      colors=[ROOF_GLASS], fill_mode="solid"), static=True)
    verts, tris = _cyl(WHEEL_RADIUS, WHEEL_WIDTH, axis="y")
    centers = [
        ( WB / 2,  track / 2, WHEEL_RADIUS), ( WB / 2, -track / 2, WHEEL_RADIUS),
        (-WB / 2,  track / 2, WHEEL_RADIUS), (-WB / 2, -track / 2, WHEEL_RADIUS),
    ]
    for name, c in zip(["fl", "fr", "rl", "rr"], centers):
        rr.log(f"/world/car_baseline/wheel_{name}",
               rr.Mesh3D(vertex_positions=verts + np.array(c, dtype=np.float32),
                         triangle_indices=tris,
                         vertex_colors=np.tile(np.array(WHEEL_COLOR, dtype=np.uint8),
                                               (len(verts), 1))),
               static=True)
    rr.log("/world/car_baseline/headlights",
           rr.Boxes3D(centers=[[L / 2 * 0.96,  W / 2 * 0.75, WHEEL_RADIUS + 0.45],
                                [L / 2 * 0.96, -W / 2 * 0.75, WHEEL_RADIUS + 0.45]],
                      half_sizes=[[0.05, 0.18, 0.06]] * 2,
                      colors=[HEADLIGHT] * 2, fill_mode="solid"), static=True)
    rr.log("/world/car_baseline/taillights",
           rr.Boxes3D(centers=[[-L / 2 * 0.96,  W / 2 * 0.75, WHEEL_RADIUS + 0.55],
                                [-L / 2 * 0.96, -W / 2 * 0.75, WHEEL_RADIUS + 0.55]],
                      half_sizes=[[0.05, 0.20, 0.05]] * 2,
                      colors=[TAILLIGHT] * 2, fill_mode="solid"), static=True)


def _log_ground(runs: list[RunResult]) -> None:
    all_x = np.concatenate([r.x for r in runs])
    all_y = np.concatenate([r.y for r in runs])
    cx, cy = (all_x.min() + all_x.max()) / 2, (all_y.min() + all_y.max()) / 2
    half = max(np.ptp(all_x), np.ptp(all_y), 200) / 2 + 50
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

    for r in runs:
        line = np.column_stack([r.x, r.y, np.full(len(r.x), 0.02 if r.is_baseline else
                                                  (0.04 if r.is_truth else 0.06))])
        radius = 0.30 if r.is_truth else (0.28 if r.is_baseline else 0.22)
        rr.log(f"/world/ground/path/{_safe(r.name)}",
               rr.LineStrips3D([line], colors=[r.color_rgb], radii=radius),
               static=True)


def _safe(name: str) -> str:
    return name.replace("/", "_").replace(" ", "_").replace(":", "_")


def _chase_cam(x: float, y: float, psi: float,
               back: float = 10.0, up: float = 4.0) -> tuple[np.ndarray, np.ndarray]:
    fwd = np.array([math.cos(psi), math.sin(psi)])
    pos = np.array([x - back * fwd[0], y - back * fwd[1], up])
    target = np.array([x + 2.0 * fwd[0], y + 2.0 * fwd[1], WHEEL_RADIUS + 0.6])
    forward = target - pos; forward /= np.linalg.norm(forward)
    right = np.cross(forward, [0, 0, 1.0]); right /= np.linalg.norm(right)
    down = np.cross(forward, right); down /= np.linalg.norm(down)
    mat = np.column_stack([right, down, forward]).astype(np.float32)
    return pos.astype(np.float32), mat


def render(seg: Segment, df: pd.DataFrame, schema: Schema, runs: list[RunResult],
           spawn: bool = False, out_path: Path | None = None) -> Path | None:
    """Log the scene + telemetry plots to rerun. If spawn=False, save .rrd."""
    if seg.platform not in CAR_DIMS:
        raise SystemExit(f"No CAR_DIMS for {seg.platform}.")
    dims = CAR_DIMS[seg.platform]

    out_dir = (out_path.parent if out_path else (OUT_ROOT / seg.slug))
    out_dir.mkdir(parents=True, exist_ok=True)
    rrd_path = out_path if out_path else (out_dir / "compare.rrd")

    rr.init(f"sim_vs_real_compare_{seg.platform.lower()}", spawn=spawn)
    if not spawn:
        rr.save(str(rrd_path))

    rr.send_blueprint(_blueprint(seg, runs), make_active=True, make_default=True)
    rr.log("/world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
    rr.log("/world/chase_cam",
           rr.Pinhole(focal_length=600, width=1280, height=720), static=True)

    _log_ground(runs)
    _log_car_static(dims)

    # Per-run plot styling
    for r in runs:
        name = _safe(r.name)
        rr.log(f"/plots/yaw_rate/{name}",
               rr.SeriesLines(colors=[r.color_rgb], names=[r.name],
                              widths=[2.0 if r.is_truth else 1.4]),
               static=True)
        if not r.is_truth:
            rr.log(f"/plots/yaw_resid/{name}",
                   rr.SeriesLines(colors=[r.color_rgb], names=[r.name], widths=[1.4]),
                   static=True)
            rr.log(f"/plots/xy_err/{name}",
                   rr.SeriesLines(colors=[r.color_rgb], names=[r.name], widths=[1.4]),
                   static=True)
    rr.log("/plots/inputs/v",
           rr.SeriesLines(colors=[(120, 120, 120)], names=["v_mps"], widths=[1.2]),
           static=True)
    rr.log("/plots/inputs/delta",
           rr.SeriesLines(colors=[(120, 120, 120)], names=["delta_road_rad"], widths=[1.2]),
           static=True)

    # Time loop. Camera follows the V0 baseline (or first run if no baseline).
    primary = next((r for r in runs if r.is_baseline), runs[0])
    truth = next((r for r in runs if r.is_truth), None)
    t = df["t_s"].to_numpy()
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()

    for i in range(len(t)):
        rr.set_time("sim_time", duration=float(t[i]))
        rr.log("/world/car_baseline",
               rr.Transform3D(translation=[float(primary.x[i]), float(primary.y[i]), 0.0],
                              rotation=rr.RotationAxisAngle(axis=[0, 0, 1.0],
                                                             angle=rr.Angle(rad=float(primary.psi[i])))))
        cam_pos, cam_mat = _chase_cam(float(primary.x[i]), float(primary.y[i]),
                                      float(primary.psi[i]))
        rr.log("/world/chase_cam",
               rr.Transform3D(translation=cam_pos.tolist(), mat3x3=cam_mat.tolist()))

        for r in runs:
            name = _safe(r.name)
            rr.log(f"/world/pose/{name}",
                   rr.Points3D([[float(r.x[i]), float(r.y[i]), WHEEL_RADIUS + 0.7]],
                               colors=[r.color_rgb],
                               radii=(0.7 if r.is_truth else 0.5),
                               labels=[r.name]))
            rr.log(f"/plots/yaw_rate/{name}", rr.Scalars(float(r.yaw_rate[i])))
            if not r.is_truth and truth is not None:
                rr.log(f"/plots/yaw_resid/{name}",
                       rr.Scalars(float(r.yaw_rate[i] - truth.yaw_rate[i])))
                err = math.hypot(r.x[i] - truth.x[i], r.y[i] - truth.y[i])
                rr.log(f"/plots/xy_err/{name}", rr.Scalars(err))
        rr.log("/plots/inputs/v", rr.Scalars(float(v[i])))
        rr.log("/plots/inputs/delta", rr.Scalars(float(delta[i])))

    if not spawn:
        return rrd_path
    return None


def _blueprint(seg: Segment, runs: list[RunResult]) -> rrb.Blueprint:
    chase = rrb.EyeControls3D(
        kind=Eye3DKind.FirstPerson, tracking_entity="/world/chase_cam",
    )
    return rrb.Blueprint(
        rrb.Horizontal(
            rrb.Vertical(
                rrb.TimeSeriesView(origin="/plots/yaw_rate", name="Yaw rate (rad/s)"),
                rrb.TimeSeriesView(origin="/plots/yaw_resid", name="Yaw-rate residual"),
                rrb.TimeSeriesView(origin="/plots/xy_err", name="XY error vs measured (m)"),
                rrb.Horizontal(
                    rrb.TimeSeriesView(origin="/plots/inputs/v", name="Speed (m/s)"),
                    rrb.TimeSeriesView(origin="/plots/inputs/delta", name="δ_road (rad)"),
                ),
            ),
            rrb.Spatial3DView(
                origin="/world",
                name=f"3D — {seg.platform}",
                eye_controls=chase,
            ),
            column_shares=[1, 1],
        ),
    )
