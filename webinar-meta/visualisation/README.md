# Visualisation toolkit — compare N agents on one segment

Adapted from `KB003/code/viz_compare_{rerun,plotly}.py`. Given one segment of
real driving data and any number of agents (each shipping a
`final-model/predict.py`), overlays every agent's predicted yaw rate +
integrated trajectory against the measured truth and the V0 kinematic
baseline.

## Setup

Needs Python 3.11+ and:

```bash
pip install numpy pandas plotly rerun-sdk
```

(`rerun-sdk` is only required if you want the 3D backend.)

## Quick start

```bash
cd webinar-meta/visualisation

# 1. List every available segment (index, platform, device, route, idx)
python compare.py list
python compare.py list --platform HYUNDAI_IONIQ_5

# 2. Compare a handful of agents on segment #12 → plotly HTML
python compare.py 12 \
    --agent module-1/agent-01 \
    --agent module-3/agent-01

# 3. Same comparison, open the rerun 3D viewer live
python compare.py 12 \
    --agent module-1/agent-01 \
    --agent module-3/agent-01 \
    --spawn

# 4. Save an .rrd for later sharing/reopening
python compare.py 12 --agent module-1/agent-01 --rrd
```

Outputs land under `webinar-meta/visualisation/out/<segment_slug>/`.

## Agent specs

An agent is any directory under `webinar-AI/` containing
`final-model/predict.py` (or `predict.py` at the top level) exporting
`predict(sim_df, platform) -> DataFrame` with at least
`yaw_rate_pred_rads`. Optional: `x_m`, `y_m` (otherwise the runner
re-integrates from yaw + measured speed).

Spec forms:

```text
module-1/agent-01                          # path; legend = "module-1/agent-01"
module-3/agent-05:M3 agent-05              # path:label
/abs/path/to/some-agent-root               # absolute path
```

The V0 baseline (the `x_m`/`y_m`/`yaw_rate_pred_rads` already in the CSV)
and measured truth are added automatically; you do not need to list them.

## Presets

A preset is a JSON file under `presets/` capturing a reusable agent list
(and optionally a default segment):

```json
{
  "segment": "5",
  "agents": [
    "module-1/agent-01:M1 V1",
    "module-3/agent-01:M3 flagship"
  ]
}
```

Run it:

```bash
python compare.py --preset cohort-flagships --html      # use preset's segment
python compare.py 7 --preset cohort-flagships --rrd     # override segment
```

Save the current invocation as a preset:

```bash
python compare.py 12 \
    --agent module-1/agent-01 \
    --agent module-3/agent-01 \
    --save-preset my-comparison
```

Two presets ship by default:

- `example.json` — one agent from M1 + one from M3, segment 0.
- `cohort-flagships.json` — agent-01 from every module (M1, M2, M3).

## Files

| File                  | Role                                                         |
|-----------------------|--------------------------------------------------------------|
| `compare.py`          | Top-level CLI dispatcher (`list`, segment + agents).         |
| `_runner.py`          | Segment discovery, agent loader, trajectory integrator.      |
| `compare_plotly.py`   | Plotly interactive HTML backend (6-panel overlay).           |
| `compare_rerun.py`    | rerun.io 3D + telemetry backend.                             |
| `presets/`            | Saved comparison configs (JSON).                             |
| `out/<seg_slug>/`     | Rendered HTML / .rrd / PNG.                                  |
