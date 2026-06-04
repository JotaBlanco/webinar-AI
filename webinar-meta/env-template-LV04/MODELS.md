# MODELS.md — candidate model registry (tree-structured)

One `##`-level entry per candidate. **Do not edit by hand** — the `iterate`
skill appends entries as you score candidates with it. Hand-edits are allowed
for the `verdict` and `notes` fields once a candidate is assessed, but the
machine fields (scores, gate, parent linkage) are owned by `iterate`.

Preflight enforces (m4.v1.01 thresholds — bumped from m4.v1):
- **≥6 entries total** (was 4 in m4.v1; bumped to reduce single-candidate
  ships per cohort §9. The 6-way launch-rungs fan-out produces this for free.)
- **≥2 entries tagged** `rung: 1` or `rung: 2` or `rung: 3` or `rung: orthogonal`
  (was 1 in m4.v1)
- ≥1 entry with `gate: pass`
- ≥4 entries written by `skills/iterate/` to EXPERIMENTS.md (the
  `iterate_history_min` gate — see `_shared/gates.py`)
- The shipped candidate's `parent` chain must reach `v1` without loops
- For any candidate whose `coeffs.json` declares a per-platform bias term,
  a `route_cv_sigma` sibling field must be present (the `bias_without_route_cv`
  gate — see cohort §6 + §9 + `_shared/gates.py`)

The relevant constants live in `skills/pre-flight-final-model/preflight.py`:
`MIN_MODELS_MD_CANDIDATES = 6`, `MIN_ITERATE_HISTORY = 4`. If you bump them
in the code, bump them here too — the smoke test `_smoke_template.sh`
cross-checks this file against the constants.

Schema (every field is populated by `iterate`):

```
## <model-name>
- dir: models/<model-name>/
- parent: <model-name-or-"v1">
- rung: 0 | 1 | 2 | 3 | orthogonal
- structure: refines-v1 | differs-from-v1
- status: drafting | gate-failed | kept | shelved | promote_to_leader | shipped
- pooled-yaw-rmse-dev: <number ± std>
- pooled-cte-rmse-dev: <number ± std>
- vs-v1: yaw +N%, CTE +N%
- vs-parent: yaw +N%, CTE +N%
- gate: pass | warn (reasons) | fail (reasons)
- next: <routing string from critique-residuals>
- notes: <one-line agent annotation, optional>
```

`structure:` is derived from `rung:` — anything with `rung: 0` whose parent
is also `rung: 0` is `refines-v1`; everything else is `differs-from-v1`.

V1's pooled-dev scores (constants — do NOT score V1 again, this is the truth
of record): `yaw_rmse = 0.005874 rad/s`, `cte_rmse = 56.81 m`.

The tree structure these entries form is also persisted in `TREE.json` —
human-readable here, machine-readable there. Use `skills/visualise-tree/` to
render either as ASCII or markdown.

---

<!-- iterate-skill appends candidate entries below this line -->
