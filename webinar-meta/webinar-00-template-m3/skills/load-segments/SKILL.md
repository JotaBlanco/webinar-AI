---
name: load-segments
description: Load `sim.csv` segment files into a list of pandas DataFrames with consistent dtype hygiene and parsed path metadata (platform / device / route / idx) attached as `df.attrs`. Resolves segments by explicit paths, an explicit glob, a platform name, or defaults to all FORD platforms. Saves ~30 lines of glob/parse/coerce boilerplate per script.
when-to-invoke: You need raw segment DataFrames in memory and want consistent column dtypes plus per-segment provenance. Use before any per-segment analysis (plotting, scoring, feature extraction). Not for splitting into train/dev — use make-train-dev-split for that.
inputs: paths (list[Path] or None), platform (str or None), glob (str or None), columns (list[str] or None).
outputs: list[pandas.DataFrame] sorted by segment_path. Each df has df.attrs populated with segment_path, platform, device, route, idx.
load-cost: ~110 tokens metadata, ~150 tokens body.
---

# load-segments

## What it does

`load(...)` resolves a set of `sim.csv` files and returns them as a list of DataFrames, sorted by path for determinism. Resolution order:

1. If `paths` is given, use exactly those.
2. Else if `glob` is given, resolve `data/sim-full/<glob>` relative to the working directory.
3. Else if `platform` is given, glob `data/sim-full/<platform>/**/sim.csv`.
4. Else, glob `data/sim-full/FORD_*/**/sim.csv`.

Each DataFrame has:

- Critical numeric columns coerced to float: `t_s`, `v_mps`, `delta_road_rad`, `yaw_rate_meas_rads`, `yaw_rate_pred_rads` (missing columns are tolerated, not coerced).
- Rows with NaN in `t_s` or `v_mps` dropped.
- `df.attrs["segment_path"]` (Path), `df.attrs["platform"]`, `df.attrs["device"]`, `df.attrs["route"]`, `df.attrs["idx"]` (all strings) parsed from the path.

If `columns` is given, only those columns are read (saves memory). If the column list is partially missing in a file, the skill warns once and falls back to loading every column.

If no `sim.csv` matches, raises `FileNotFoundError` with the resolved selector in the message.

## What it does not do

- It does not score, plot, or split your data.
- It does not invent columns. If a critical column is missing, downstream code sees the absence.
- It does not cache between calls.

## Usage

```python
from skills.load_segments.load import load

dfs = load(platform="FORD_MUSTANG_MACH_E_MK1", columns=["t_s", "v_mps", "yaw_rate_meas_rads"])
print(len(dfs), "segments")
print(dfs[0].attrs)            # {'segment_path': PosixPath(...), 'platform': '...', ...}
print(dfs[0].head())
```

## Smoke test

`python3 _smoke.py` from inside this skill directory. Loads Mach-E segments and asserts shape, dtypes, and attrs.

This is a starting point. Modify, extend, or replace as your task demands.
