---
name: pre-flighting-final-model
description: Sanity-check that a `final-model/` deliverable bundle is shaped the way the task brief requires. Verifies required files exist (`predict.py`, `manifest.json`, `REPORT.md`), `predict.py` imports cleanly with siblings on sys.path, the configured `predict_callable` resolves, its signature accepts `(sim_df, platform)`, and a real-segment dry-run returns a DataFrame with `yaw_rate_pred_rads`, the original index, and no NaN. Returns a structured pass/fail report — never raises on individual check failures.
when-to-invoke: You think your `final-model/` is done and want to catch dumb mistakes (missing files, broken imports, wrong return shape) before declaring the deliverable shipped. Run it last, after you have written `predict.py`, `manifest.json`, and `REPORT.md`.
when-NOT-to-invoke: You want to score model quality (use scoring-model). You want to validate intermediate states of `predict.py` during iteration — this is for the final bundle, not the inner loop.
inputs: final_model_dir (str or Path) — directory holding the bundle to check.
outputs: dict with keys `passes` (bool), `checks` (list of `{name, status, detail}`), `errors` (list of str).
load-cost: ~150 tokens metadata, ~170 tokens body.
---

# pre-flight-final-model

## What it does

`preflight(final_model_dir)` runs nine checks in order against a candidate `final-model/` bundle:

1. `directory_exists` — the directory is present.
2. `predict_py_present` — `predict.py` exists.
3. `manifest_json_present` — `manifest.json` exists.
4. `report_md_present` — `REPORT.md` exists and is ≥ 100 bytes.
5. `manifest_parses` — JSON parses, has `platform_support` (list[str]) and `predict_callable` (`"<file>:<fn>"`).
6. `predict_imports` — loads `predict.py` via `importlib.util`, with `final_model_dir` temporarily on `sys.path` so sibling imports (helpers, coeffs) work.
7. `predict_callable_exists` — the function named by `predict_callable` (default `predict`) exists and is callable.
8. `predict_signature_compatible` — signature accepts at least `(sim_df, platform)` positionally, or uses `**kwargs`.
9. `predict_returns_correct_shape` — calls `predict` on the first `data/sim-only/FORD_MUSTANG_MACH_E_MK1/**/sim.csv` (alphabetical). Asserts the return is a `pandas.DataFrame` with column `yaw_rate_pred_rads`, an index identical to the input, no NaN in `yaw_rate_pred_rads`, and no NaN in `x_m`/`y_m` if present.

Each check is wrapped in its own try/except — a failure becomes `status="fail"` with the truncated exception in `detail`. If a check's prerequisite failed, the dependent check is recorded as `status="skip"` and `passes` is forced to `False`.

## What it does not do

- It does not score quality (use `score-model` for that).
- It does not run on multiple platforms — just one sample segment to prove the function works end-to-end.
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
