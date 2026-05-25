# evals

Computational sensors. Deterministic checks that score a skill's output against a known-good fixture and emit a binary pass/fail with a labelled failure mode. Used by angles 01 (M4 — sensor + self-patching skill) and 04 (M3 — regression guard).

## Naming convention

`<skill-name>_eval.py` — one eval per skill that needs one. The eval lives here, not inside the skill folder, so the skill stays portable and the eval can be versioned independently.

## Contract

Every eval module exposes a single function:

```python
def evaluate(skill_output: dict, fixture_path: str) -> dict:
    """
    Returns: {
        "passed": bool,
        "failure_mode": str | None,   # one of a named enum per eval
        "evidence": dict,             # the specific numbers backing the verdict
    }
    """
```

The agent calls `evaluate()` after running the skill. On `passed=False` it patches the skill markdown using `failure_mode` + `evidence` as the context — that is the NC-21 self-patching loop the workshop demonstrates.

## Computational first, inferential second (NC-15)

- **Computational sensors** — deterministic Python checks, milliseconds, no LLM. Always run first. Cheap.
- **Inferential sensors** — LLM-as-judge, slower, expensive. Run only where computational checks cannot decide.

Most evals here should be computational. Inferential evals belong as `SKILL.md` files under `skills/judges/<name>/` so they can be versioned and improved like any other skill.

## Files

- `hello_world_eval.py` — for `skills/hello-world/`. Checks the smoke-test answer numerically. Delete with the hello-world skill once your first real eval is in place.
