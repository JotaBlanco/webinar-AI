---
name: pre-flighting-final-model
description: Sanity-check that a `final-model/` deliverable bundle is shaped the way the task brief requires. Verifies required files exist (`predict.py`, `manifest.json`, `REPORT.md`), `predict.py` imports cleanly with siblings on sys.path, the configured `predict_callable` resolves, its signature accepts `(sim_df, platform)`, the predict dry-runs on every platform declared in `manifest.platform_support` (against `data/sim-only/` so allowlist violations surface here too), `EXPERIMENTS.md` opens with an "Alternatives considered" block listing ≥5 candidate model shapes (≥3 tagged structurally distinct from V1), `MODELS.md` registers ≥3 candidates (≥1 tagged `structure: differs-from-v1`), and the shipped predict differs from V1 by more than a small tolerance on a sample segment. Returns a structured pass/fail report — never raises on individual check failures.
when-to-invoke: You think your `final-model/` is done and want to catch dumb mistakes (missing files, broken imports, wrong return shape) before declaring the deliverable shipped. Run it last, after you have written `predict.py`, `manifest.json`, and `REPORT.md`.
when-NOT-to-invoke: You want to score model quality (use scoring-model). You want to validate intermediate states of `predict.py` during iteration — this is for the final bundle, not the inner loop.
inputs: final_model_dir (str or Path) — directory holding the bundle to check.
outputs: dict with keys `passes` (bool), `checks` (list of `{name, status, detail}`), `errors` (list of str).
load-cost: ~150 tokens metadata, ~170 tokens body.
---

# pre-flight-final-model

## What it does

`preflight(final_model_dir)` runs twelve checks in order against a candidate `final-model/` bundle:

1. `directory_exists` — the directory is present.
2. `predict_py_present` — `predict.py` exists.
3. `manifest_json_present` — `manifest.json` exists.
4. `report_md_present` — `REPORT.md` exists and is ≥ 100 bytes.
5. `manifest_parses` — JSON parses, has `platform_support` (list[str]) and `predict_callable` (`"<file>:<fn>"`).
6. `predict_imports` — loads `predict.py` via `importlib.util`, with `final_model_dir` temporarily on `sys.path` so sibling imports (helpers, coeffs) work.
7. `predict_callable_exists` — the function named by `predict_callable` exists and is callable.
8. `predict_signature_compatible` — signature accepts at least `(sim_df, platform)` positionally, or uses `**kwargs`.
9. `predict_returns_correct_shape` — calls `predict` once per platform declared in `manifest.platform_support`. Asserts the return is a `pandas.DataFrame` with column `yaw_rate_pred_rads`, index identical to the input, no NaN. Catches platform-conditional failures.
10. `experiments_md_has_alternatives_header` *(new in m3.v3)* — looks for `EXPERIMENTS.md` and checks it opens with a heading "Alternatives considered" containing ≥5 bullets, of which ≥3 are tagged structurally distinct from V1 (via `(structure)` or `structure: differs-from-v1`). Enforces the upstream option-generation discipline from `references/exploration-discipline.md`.
11. `models_md_has_three_candidates` *(new in m3.v3)* — looks for `MODELS.md` and checks it has ≥3 `##`-level candidate entries, with ≥1 tagged `structure: differs-from-v1`. Enforces the "models as first-class objects" workflow from AGENTS.md.
12. `predict_differs_structurally_from_v1` *(new in m3.v3, warn-only)* — calls the shipped predict and `code.v1_baseline.predict_v1` on the same sample segment and compares pointwise yaw output. Warns (not fails) if max abs diff < 1e-3 rad/s — that pattern usually means "I refit V1 and shipped it". The warn lets agents ship V1 explicitly when all candidates lost, but forces the choice to be documented in REPORT.md.

Each check is wrapped in its own try/except — failures become `status="fail"`, transient/optional failures become `status="warn"` (still pass), skipped checks become `status="skip"` (force `passes=False`).

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
