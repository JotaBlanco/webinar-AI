"""load-segments: resolve sim.csv files and return a list of dtype-clean DataFrames.

The exported function is `load(...)`. See SKILL.md for the full contract.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import pandas as pd


# Columns we expect to be numeric on (almost) every segment. Missing columns are
# tolerated — they just don't get coerced.
_CRITICAL_FLOAT_COLS = (
    "t_s",
    "v_mps",
    "delta_road_rad",
    "yaw_rate_meas_rads",
    "yaw_rate_pred_rads",
)

# Rows must have these to be useful at all.
_REQUIRED_NONNA_COLS = ("t_s", "v_mps")

# Base directory where segments live, relative to the working directory.
_SEGMENTS_ROOT = Path("data") / "sim-full"


def _parse_path_attrs(sim_csv: Path) -> dict:
    """Pull platform / device / route / idx out of a sim.csv path.

    Path schema (indexed from the right):
        .../<PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv
    """
    parts = sim_csv.parts
    # parts[-1] == 'sim.csv', parts[-2] == idx, etc.
    return {
        "segment_path": sim_csv,
        "platform": parts[-5] if len(parts) >= 5 else "",
        "device": parts[-4] if len(parts) >= 4 else "",
        "route": parts[-3] if len(parts) >= 3 else "",
        "idx": parts[-2] if len(parts) >= 2 else "",
    }


def _resolve_paths(
    paths: Optional[Sequence[Path]],
    platform: Optional[str],
    glob: Optional[str],
) -> tuple[List[Path], str]:
    """Resolve which sim.csv files to load and return (paths, human-readable selector)."""
    if paths:
        resolved = [Path(p) for p in paths]
        selector = f"explicit paths (n={len(resolved)})"
        return resolved, selector

    if glob is not None:
        pattern = str(_SEGMENTS_ROOT / glob)
        resolved = sorted(Path(".").glob(str(_SEGMENTS_ROOT / glob)))
        selector = f"glob: {pattern}"
        return resolved, selector

    if platform is not None:
        pattern = str(_SEGMENTS_ROOT / platform / "**" / "sim.csv")
        resolved = sorted(Path(".").glob(pattern))
        selector = f"platform glob: {pattern}"
        return resolved, selector

    pattern = str(_SEGMENTS_ROOT / "FORD_*" / "**" / "sim.csv")
    resolved = sorted(Path(".").glob(pattern))
    selector = f"default glob: {pattern}"
    return resolved, selector


def _read_one(sim_csv: Path, columns: Optional[Sequence[str]], _warned: dict) -> pd.DataFrame:
    """Read a single sim.csv with the requested columns, falling back if some are missing."""
    if columns is not None:
        try:
            df = pd.read_csv(sim_csv, usecols=list(columns))
        except (ValueError, KeyError):
            # Some requested column isn't in this file. Fall back to loading everything,
            # but only warn once per call.
            if not _warned.get("missing_cols"):
                warnings.warn(
                    "load-segments: requested columns not all present in some files; "
                    "falling back to loading every column. "
                    "(This warning fires once per call.)",
                    stacklevel=3,
                )
                _warned["missing_cols"] = True
            df = pd.read_csv(sim_csv)
    else:
        df = pd.read_csv(sim_csv)

    # Coerce critical numerics to float where present.
    for col in _CRITICAL_FLOAT_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)

    # Drop rows that have NaN in the always-needed columns.
    drop_cols = [c for c in _REQUIRED_NONNA_COLS if c in df.columns]
    if drop_cols:
        df = df.dropna(subset=drop_cols).reset_index(drop=True)

    # Attach provenance.
    df.attrs.update(_parse_path_attrs(sim_csv))
    return df


def load(
    paths: Optional[Sequence[Path]] = None,
    platform: Optional[str] = None,
    glob: Optional[str] = None,
    columns: Optional[Sequence[str]] = None,
) -> List[pd.DataFrame]:
    """Load segment sim.csv files into a list of DataFrames.

    Parameters
    ----------
    paths
        Explicit list of sim.csv paths. If given (and non-empty), other selectors are ignored.
    platform
        Platform directory name (e.g. "FORD_MUSTANG_MACH_E_MK1"). Used when `paths` and
        `glob` are both None.
    glob
        Explicit glob string under `data/sim-full/`. Takes precedence over `platform`.
    columns
        If given, only these columns are read. If some are missing in some files, the
        skill warns once and reads every column for those files.

    Returns
    -------
    list[pd.DataFrame]
        Sorted by segment_path for determinism. Each df has df.attrs populated with
        segment_path (Path), platform, device, route, idx (all str).

    Raises
    ------
    FileNotFoundError
        If no sim.csv matches the resolved selector.
    """
    resolved, selector = _resolve_paths(paths, platform, glob)

    if not resolved:
        raise FileNotFoundError(
            f"load-segments: no sim.csv matched {selector}. "
            f"Working directory: {Path.cwd()}"
        )

    # Sort by path string for determinism (already sorted from glob, but be explicit
    # for the explicit-paths case too).
    resolved = sorted(resolved, key=str)

    _warned: dict = {}
    dfs = [_read_one(p, columns, _warned) for p in resolved]
    return dfs


__all__ = ["load"]
