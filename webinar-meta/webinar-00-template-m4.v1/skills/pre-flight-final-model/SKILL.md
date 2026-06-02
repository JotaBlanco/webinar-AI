---
name: pre-flighting-final-model
description: Sanity-check that a `final-model/` deliverable bundle is shaped the way the task brief requires. Verifies required files exist (`predict.py`, `manifest.json`, `REPORT.md`), `predict.py` imports cleanly with siblings on sys.path (this is where missing-coeffs.json failures surface), the configured `predict_callable` resolves, its signature accepts `(sim_df, platform)`, the predict dry-runs on every platform declared in `manifest.platform_support` (against `data/sim-only/` so allowlist violations like reading `a_lat_meas_mps2` surface here too), and `EXPERIMENTS.md` contains at least one logged structural-climb attempt (`Rung: 1+` or `Rung: orthogonal`). Returns a structured pass/fail report — never raises on individual check failures.
when-to-invoke: You think your `final-model/` is done and want to catch dumb mistakes (missing files, broken imports, wrong return shape) before declaring the deliverable shipped. Run it last, after you have written `predict.py`, `manifest.json`, and `REPORT.md`.
when-NOT-to-invoke: You want to score model quality (use scoring-model). You want to validate intermediate states of `predict.py` during iteration — this is for the final bundle, not the inner loop.
inputs: final_model_dir (str or Path) — directory holding the bundle to check.
outputs: dict with keys `passes` (bool), `checks` (list of `{name, status, detail}`), `errors` (list of str).
load-cost: ~150 tokens metadata, ~170 tokens body.
---

# pre-flight-final-model

## What it does

`preflight(final_model_dir)` runs ten checks in order against a candidate `final-model/` bundle:

1. `directory_exists` — the directory is present.
2. `predict_py_present` — `predict.py` exists.
3. `manifest_json_present` — `manifest.json` exists.
4. `report_md_present` — `REPORT.md` exists and is ≥ 100 bytes.
5. `manifest_parses` — JSON parses, has `platform_support` (list[str]) and `predict_callable` (`"<file>:<fn>"`).
6. `predict_imports` — loads `predict.py` via `importlib.util`, with `final_model_dir` temporarily on `sys.path` so sibling imports (helpers, coeffs) work.
7. `predict_callable_exists` — the function named by `predict_callable` (default `predict`) exists and is callable.
8. `predict_signature_compatible` — signature accepts at least `(sim_df, platform)` positionally, or uses `**kwargs`.
9. `predict_returns_correct_shape` — calls `predict` once per platform declared in `manifest.platform_support`, on the first alphabetical `data/sim-only/segments/<PLATFORM>/**/sim.csv` per platform. Asserts the return is a `pandas.DataFrame` with column `yaw_rate_pred_rads`, an index identical to the input, no NaN in `yaw_rate_pred_rads`, and no NaN in `x_m`/`y_m` if present. Catches platform-conditional failures (a predict that works on Mach-E but raises on IONIQ, etc.). Platforms with no sample data under `data/sim-only/` are skipped without failing the check.
10. `experiments_md_has_rung_climb_attempt` — looks for `EXPERIMENTS.md` (at `final_model_dir.parent`, then cwd, then bundle) and greps for at least one entry tagged `Rung: 1`, `Rung: 2`, `Rung: 3`, or `Rung: orthogonal`. Enforces the "default is to climb" policy from AGENTS.md § "On exploration" — the cohort needs evidence about rung 1, and that evidence only arrives if agents log climb attempts. The shipped model can still be rung 0; only the *attempt* has to be logged.

### m4 additional checks

11. `models_md_has_min_candidates` — `MODELS.md` has ≥4 candidate entries with at least one tagged `rung: 1`, `rung: 2`, or `rung: orthogonal`. Enforces structural diversity at the registry level, not just the experiment-log level.
12. `tree_json_consistent` — every model entry in `MODELS.md` has a corresponding node in `TREE.json` and vice versa. Catches the failure mode of editing `MODELS.md` by hand without going through `iterate`.
13. `tree_has_diverse_rungs` — `TREE.json` contains nodes from ≥2 distinct rung values (e.g. `0` + `orthogonal`, or `0` + `1`). Catches the m3.v2 / m3.v3 cohort failure of piling up at rung 0.
14. `rpi_artifacts_locked_if_present` — if `rpi/artifacts/RESEARCH.md` or `PLAN.md` exist, both must be non-writable (the RPI lock gate). If you ran RPI, you must have locked the artifacts.
15. `test_split_gate` — *only when invoked with `--final`* — scores the shipped `predict.py` on the frozen test split (`data/sim-only/test/` and `data/sim/test/`) and adds the test pooled scores to the report. Warns if `(dev - test) / dev > 5%` on either KPI — that's the canonical overfit signal under the route-grouped CV σ band. Without `--final`, the test split is never read.

Each check is wrapped in its own try/except — a failure becomes `status="fail"` with the truncated exception in `detail`. If a check's prerequisite failed, the dependent check is recorded as `status="skip"` and `passes` is forced to `False`.

## What it does not do

- It does not score quality (use `score-model` for that).
- It does not modify the bundle.

## Usage

```python
from skills.pre_flight_final_model.preflight import preflight

result = preflight("final-model")
if not result["passes"]:
    for err in result["errors"]:
        print("FAIL:", err)
```

## Smoke test

`python3 _smoke.py` from this directory. Builds a valid bundle in a temp dir and asserts `passes=True`, then breaks it and asserts `passes=False`.

## Extending this skill

This skill effectively *is* the deliverable contract for the lateral-fidelity task. If you change what a valid `final-model/` looks like (different files, different manifest schema, different predict signature), this is the single place to update.
