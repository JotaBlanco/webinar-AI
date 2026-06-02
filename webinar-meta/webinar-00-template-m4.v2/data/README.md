# data

Sim data tree for the lateral-fidelity task. Read-only. Symlinked into this
template from the project's top-level `data/` directory — `git status` should
not show changes here.

If empty: `rm -rf data/ && ln -s /path/to/project/data ./data`

## Expected layout

```
data/
├── raw/                       (raw rlogs — adapter source)
├── sim-only/
│   ├── segments/              (input-only DEV view — what predict() sees)
│   │   └── <PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv
│   └── test/                  (input-only TEST view — frozen)
│       └── <PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv
└── sim/
    ├── segments/              (full-fidelity DEV view including truth)
    │   └── <PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv
    └── test/                  (full-fidelity TEST view — frozen)
        └── <PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv
```

## Test-split layout discipline — LOAD-BEARING

The frozen test split MUST live at `data/sim-only/test/` and
`data/sim/test/` — exactly those paths. The `score-model` skill's
test-split refusal (`TestSplitDeniedError`) looks for the substrings
`sim-only/test` and `sim/test` in the path. **If the test split moves
elsewhere (e.g. `data/test-split/` or `data/sim/segments/test/`), the
refusal silently no-ops and the discipline collapses.**

Before the cohort runs, verify the layout matches. The test-split markers
that score.py checks are defined at:

```python
# skills/score-model/score.py
TEST_SPLIT_MARKER_PARTS = ("sim-only/test", "sim/test")
```

If your project uses a different layout, edit that constant — but make it
loud, not silent. The discipline only holds if every test-split path
contains one of the markers.

## The operating contract

`sim-only/segments/` is the **agent-facing view of the input** — what the
canonical grader hands to your `predict()`. The truth channel
(`yaw_rate_meas_rads`) and its kinematic shadow (`a_lat_meas_mps2`) don't
exist in these files. If your predict tries to read them, you get a
`KeyError`.

`sim/segments/` is for **scoring & training tooling only** — the local
`score-model/` skill reads truth from here, strips inputs to the allowlist,
then calls your predict. Same dual-file pattern as the canonical grader.
Your local RMSE will match the canonical RMSE.

`sim-only/test/` and `sim/test/` are **frozen** — denied to `score()` and
`score_cv()` unless invoked with `final=True`, which is only allowed from
`pre-flight-final-model --final`. The test split is the agent's honest
stopping signal under the m4 closed-loop iteration count; reading it during
iteration defeats the whole point.

Every skill in `skills/` that touches data assumes the
`<PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv` shape. Platform is the
3rd-from-rightmost directory; route is the 2nd-from-rightmost.
