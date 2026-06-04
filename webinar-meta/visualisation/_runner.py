"""Shared discovery + agent-loading helpers for the comparison backends.

A "segment" is one (platform, device, route, idx) under data/sim/segments/.
An "agent" is a final-model directory shipping `predict.py` with a callable
`predict(sim_df, platform) -> DataFrame` (containing at least
`yaw_rate_pred_rads`; optionally `x_m`, `y_m`).

This module hands the backends:
- discover_segments()         -> list[Segment]
- load_segment(seg)           -> (df, schema)
- resolve_agent(spec)          -> AgentSpec
- run_agent(agent, df, plat)  -> RunResult   (yaw_rate_pred + integrated x,y)
- compute_real_trajectory(...) -> (N,3) measured (x,y,psi)
- baseline_v0(...)             -> RunResult for the V0 sim baseline already in the CSV

The runner does not depend on a specific plot library.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]            # webinar-AI/
SIMDATA_ROOT = ROOT / "data" / "sim"
PRESETS_DIR = Path(__file__).resolve().parent / "presets"

# Approximate published vehicle dimensions, used by the rerun 3D scene.
CAR_DIMS: dict[str, dict] = {
    "TESLA_MODEL_3":           {"L": 4.694, "W": 1.849, "H": 1.443, "WB": 2.875, "track": 1.580, "color": (200,  30,  30)},
    "FORD_F_150_LIGHTNING_MK1":{"L": 5.910, "W": 2.029, "H": 1.999, "WB": 3.706, "track": 1.730, "color": (220, 220, 230)},
    "FORD_MUSTANG_MACH_E_MK1": {"L": 4.713, "W": 1.881, "H": 1.621, "WB": 2.984, "track": 1.620, "color": ( 40,  70, 170)},
    "HYUNDAI_IONIQ_5":         {"L": 4.635, "W": 1.890, "H": 1.605, "WB": 3.000, "track": 1.628, "color": (180, 180,  60)},
}

# Default agent colour palette (skip the first two; they're reserved for
# measured-truth (black) and V0-baseline (blue)).
PALETTE_HEX = [
    "#e6194B", "#3cb44b", "#ffe119", "#911eb4", "#f58231",
    "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990",
]
PALETTE_RGB = [
    (230,  25,  75), ( 60, 180,  75), (255, 225,  25), (145,  30, 180), (245, 130,  48),
    ( 66, 212, 244), (240,  50, 230), (191, 239,  69), (250, 190, 212), ( 70, 153, 144),
]


# ---------------------------------------------------------------------------
# Segment discovery
# ---------------------------------------------------------------------------

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

    @property
    def label(self) -> str:
        return f"{self.platform} · {self.device[:8]} · {self.route[:12]} · #{self.idx}"


def discover_segments() -> list[Segment]:
    """Walk every manifest.json under data/sim/segments/."""
    out: list[Segment] = []
    for manifest_path in sorted(SIMDATA_ROOT.glob("segments/*/manifest.json")):
        m = json.loads(manifest_path.read_text())
        platform = m["platform"]
        for seg in m["segments"]:
            out.append(Segment(
                platform=platform,
                device=seg["device"],
                route=seg["route"],
                idx=str(seg["idx"]),
                csv_path=SIMDATA_ROOT / seg["csv_path"],
            ))
    return out


def pick_segment(segments: list[Segment], spec: str | int) -> Segment:
    """Locate a segment by integer index, slug, or partial substring match."""
    if isinstance(spec, int):
        if not (0 <= spec < len(segments)):
            raise SystemExit(f"--segment index out of range [0,{len(segments)}).")
        return segments[spec]
    if spec.isdigit():
        return pick_segment(segments, int(spec))
    # substring against slug or label
    matches = [s for s in segments if spec in s.slug or spec in s.label]
    if not matches:
        raise SystemExit(f"No segment matches {spec!r}. Try `compare.py list`.")
    if len(matches) > 1 and not any(spec == s.slug for s in matches):
        names = ", ".join(s.slug for s in matches[:5])
        raise SystemExit(f"Ambiguous segment {spec!r}, matches: {names}...")
    for s in matches:
        if spec == s.slug:
            return s
    return matches[0]


# ---------------------------------------------------------------------------
# Schema + truth normalisation
# ---------------------------------------------------------------------------

@dataclass
class Schema:
    """Which truth/baseline columns are present in this segment's sim.csv."""
    yaw_baseline_col: str         # V0 baseline yaw rate prediction
    yaw_real_col: str | None      # measured yaw rate (Ford/Hyundai only)
    a_y_baseline_col: str | None  # V0 baseline lateral accel
    a_y_real_col: str | None      # measured lateral accel
    has_wheel_speeds: bool        # for Tesla fallback Ackermann


def resolve_schema(df: pd.DataFrame) -> Schema:
    cols = set(df.columns)
    return Schema(
        yaw_baseline_col="yaw_rate_pred_rads" if "yaw_rate_pred_rads" in cols else "psi_dot_rads",
        yaw_real_col="yaw_rate_meas_rads" if "yaw_rate_meas_rads" in cols else None,
        a_y_baseline_col="a_y_pred_mps2" if "a_y_pred_mps2" in cols else ("a_y_mps2" if "a_y_mps2" in cols else None),
        a_y_real_col="a_lat_meas_mps2" if "a_lat_meas_mps2" in cols else None,
        has_wheel_speeds="wheel_RR_kph" in cols and "wheel_RL_kph" in cols,
    )


def load_segment(seg: Segment) -> tuple[pd.DataFrame, Schema]:
    df = pd.read_csv(seg.csv_path)
    schema = resolve_schema(df)
    # Normalise the V0 baseline column name so any agent expecting
    # `yaw_rate_pred_rads` works on Tesla too.
    if "yaw_rate_pred_rads" not in df.columns and "psi_dot_rads" in df.columns:
        df = df.copy()
        df["yaw_rate_pred_rads"] = df["psi_dot_rads"]
    return df, schema


def compute_real_trajectory(df: pd.DataFrame, schema: Schema, track: float) -> np.ndarray:
    """Reconstruct measured (x,y,psi) at 50 Hz from yaw-rate (preferred) or
    wheel-speed Ackermann fallback (Tesla). Returns (N,3).
    """
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0] - (t[1] - t[0]))
    v_meas = df["v_mps"].to_numpy()
    if schema.yaw_real_col is not None:
        psi_dot = df[schema.yaw_real_col].to_numpy()
    elif schema.has_wheel_speeds:
        v_RR = df["wheel_RR_kph"].to_numpy() / 3.6
        v_RL = df["wheel_RL_kph"].to_numpy() / 3.6
        psi_dot = (v_RL - v_RR) / track
    else:
        psi_dot = np.zeros_like(t)
    psi = np.cumsum(psi_dot * dt)
    x = np.cumsum(v_meas * np.cos(psi) * dt)
    y = np.cumsum(v_meas * np.sin(psi) * dt)
    return np.column_stack([x, y, psi])


# ---------------------------------------------------------------------------
# Agent loading + execution
# ---------------------------------------------------------------------------

@dataclass
class AgentSpec:
    """A loaded agent ready to call."""
    name: str                # display label
    path: Path               # the agent directory (final-model dir)
    predict: Callable        # predict(sim_df, platform) -> DataFrame
    color_hex: str = "#000000"
    color_rgb: tuple = (0, 0, 0)
    manifest: dict = field(default_factory=dict)


def _find_predict_dir(path: Path) -> Path:
    """Accept either the agent root (containing final-model/predict.py) or
    a directory that directly contains predict.py."""
    candidates = [path / "final-model" / "predict.py", path / "predict.py"]
    for c in candidates:
        if c.exists():
            return c.parent
    raise SystemExit(f"No predict.py found under {path} (looked in final-model/).")


def resolve_agent(spec: str, default_color_idx: int = 0) -> AgentSpec:
    """Parse a `path[:label]` spec into an AgentSpec by importing predict.py.

    Path is resolved relative to the webinar-AI root if not absolute.
    """
    label = None
    if ":" in spec and not spec.startswith("/"):
        spec, label = spec.split(":", 1)
    raw = Path(spec)
    agent_root = raw if raw.is_absolute() else (ROOT / raw)
    if not agent_root.exists():
        raise SystemExit(f"Agent path not found: {agent_root}")

    predict_dir = _find_predict_dir(agent_root)
    predict_py = predict_dir / "predict.py"
    manifest_path = predict_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    # Import predict.py in isolation so each agent can shadow `_shared`,
    # `coefs.json`, etc. without clobbering its siblings.
    mod_name = f"_agent_{abs(hash(str(predict_py)))}"
    sys.path.insert(0, str(predict_dir))
    try:
        spec_obj = importlib.util.spec_from_file_location(mod_name, predict_py)
        module = importlib.util.module_from_spec(spec_obj)
        spec_obj.loader.exec_module(module)
    finally:
        sys.path.pop(0)

    if not hasattr(module, "predict"):
        raise SystemExit(f"{predict_py} has no `predict` function.")

    if label is None:
        # Derive a short label from the path: module-X/agent-YY
        rel = agent_root.relative_to(ROOT) if str(agent_root).startswith(str(ROOT)) else agent_root
        label = "/".join(rel.parts[-2:])

    idx = default_color_idx % len(PALETTE_HEX)
    return AgentSpec(
        name=label,
        path=agent_root,
        predict=module.predict,
        color_hex=PALETTE_HEX[idx],
        color_rgb=PALETTE_RGB[idx],
        manifest=manifest,
    )


@dataclass
class RunResult:
    """One row in the comparison: a yaw-rate trace + an integrated trajectory."""
    name: str
    color_hex: str
    color_rgb: tuple
    yaw_rate: np.ndarray         # (N,)
    x: np.ndarray                # (N,)
    y: np.ndarray                # (N,)
    psi: np.ndarray              # (N,)
    is_truth: bool = False
    is_baseline: bool = False


def _integrate_xy(df: pd.DataFrame, yaw_rate: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t = df["t_s"].to_numpy()
    v = df["v_mps"].to_numpy()
    dt = np.diff(t, prepend=t[0] - (t[1] - t[0]))
    psi = np.cumsum(yaw_rate * dt)
    x = np.cumsum(v * np.cos(psi) * dt)
    y = np.cumsum(v * np.sin(psi) * dt)
    return x, y, psi


def run_agent(agent: AgentSpec, df: pd.DataFrame, platform: str) -> RunResult:
    """Call agent.predict, then either use returned x/y or integrate from yaw."""
    pred = agent.predict(df, platform)
    if "yaw_rate_pred_rads" not in pred.columns:
        raise SystemExit(f"{agent.name}: predict() must return `yaw_rate_pred_rads`.")
    yaw = pred["yaw_rate_pred_rads"].to_numpy()
    if "x_m" in pred.columns and "y_m" in pred.columns:
        x = pred["x_m"].to_numpy()
        y = pred["y_m"].to_numpy()
        # Recompute psi from yaw rate for camera/heading purposes.
        t = df["t_s"].to_numpy()
        dt = np.diff(t, prepend=t[0] - (t[1] - t[0]))
        psi = np.cumsum(yaw * dt)
    else:
        x, y, psi = _integrate_xy(df, yaw)
    return RunResult(
        name=agent.name, color_hex=agent.color_hex, color_rgb=agent.color_rgb,
        yaw_rate=yaw, x=x, y=y, psi=psi,
    )


def baseline_v0(df: pd.DataFrame, schema: Schema) -> RunResult:
    """The V0 baseline already integrated in the CSV (x_m, y_m, psi_rad)."""
    return RunResult(
        name="V0 baseline (KS)",
        color_hex="#1f77b4", color_rgb=(31, 119, 180),
        yaw_rate=df[schema.yaw_baseline_col].to_numpy(),
        x=df["x_m"].to_numpy(),
        y=df["y_m"].to_numpy(),
        psi=df["psi_rad"].to_numpy(),
        is_baseline=True,
    )


def measured_truth(df: pd.DataFrame, schema: Schema, track: float) -> RunResult:
    real_xyp = compute_real_trajectory(df, schema, track)
    if schema.yaw_real_col is not None:
        yaw = df[schema.yaw_real_col].to_numpy()
    elif schema.has_wheel_speeds:
        v_RR = df["wheel_RR_kph"].to_numpy() / 3.6
        v_RL = df["wheel_RL_kph"].to_numpy() / 3.6
        yaw = (v_RL - v_RR) / track
    else:
        yaw = np.zeros(len(df))
    return RunResult(
        name="measured", color_hex="#111111", color_rgb=(20, 20, 20),
        yaw_rate=yaw, x=real_xyp[:, 0], y=real_xyp[:, 1], psi=real_xyp[:, 2],
        is_truth=True,
    )


# ---------------------------------------------------------------------------
# Preset I/O
# ---------------------------------------------------------------------------

def load_preset(name: str) -> dict:
    p = PRESETS_DIR / f"{name}.json"
    if not p.exists():
        # also accept full path
        if Path(name).exists():
            p = Path(name)
        else:
            available = ", ".join(sorted(q.stem for q in PRESETS_DIR.glob("*.json"))) or "(none)"
            raise SystemExit(f"Preset {name!r} not found in {PRESETS_DIR}. Available: {available}")
    return json.loads(p.read_text())


def save_preset(name: str, agents: list[str], segment: str | None = None) -> Path:
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    p = PRESETS_DIR / f"{name}.json"
    payload = {"agents": agents}
    if segment is not None:
        payload["segment"] = str(segment)
    p.write_text(json.dumps(payload, indent=2) + "\n")
    return p
