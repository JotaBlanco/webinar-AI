---
name: iterate
description: One-shot tree-search iteration step. Given a candidate model bundle at `models/<name>/`, runs the verifier gate (score-model with k-fold route-grouped CV on dev, residual-structure, comparison vs parent + vs V1 + vs current leader), appends a node to `TREE.json`, updates `MODELS.md` with parent linkage, appends an `EXPERIMENTS.md` entry, and returns a routing dict telling the agent what to do next. **Model-shape-agnostic** — works for any candidate whose `predict.py` matches the operating contract, whether rung-0 polish, rung-1 dynamic ODE, residual learner, or neural. The skill knows nothing about the candidate's internals; it just runs the contract and logs.
when-to-invoke: Every time you create or modify a `models/<name>/predict.py` and want to know (a) whether it beat its parent on dev CV, (b) whether the win is signal or noise (compared to CV σ), (c) what the verifier gate says about over- vs under-parameterization, (d) what the typed router recommends as the next move. Use as the *only* way candidates enter `MODELS.md` — it auto-fills the registry.
when-NOT-to-invoke: For raw scoring without registry side-effects, use `score-model` directly. For final-deliverable verification, use `pre-flight-final-model`. For one-off comparisons between two specific models, use `compare-models`.
inputs: model_dir (str or Path) — `models/<name>/`. Optional: parent (str, default = current MODELS.md leader; pass `"v1"` to compare against the V1 baseline, `"none"` to skip parent comparison). Optional: rung (int 0-3 or "orthogonal", default inferred from `notes.md`).
outputs: dict with `dev_cv` (mean ± std per platform + pooled), `vs_parent` (Δ%, signed), `vs_v1` (Δ%, signed), `gate` (`pass | warn | fail` + reasons list), `verdict` (`keep | shelve | promote_to_leader | needs_rung_climb`), `next_move` (routing string the critique-residuals skill emits). Side-effects: appends to `TREE.json`, `MODELS.md`, `EXPERIMENTS.md`.
load-cost: ~220 tokens metadata, ~480 tokens body.
---

# iterate

## What it does — the closed loop in one call

The five-step manual loop that m3.v3 cohorts kept skipping or doing inconsistently — score → diff vs parent → check gate → log → decide — is wrapped here into one tool call. Every iteration is a **scored, logged, routed** node in the tree.

```python
from skills.iterate.iterate import iterate
result = iterate("models/dyn-st-fit-Calpha")
# TREE.json now has a new node. MODELS.md has a new entry.
# EXPERIMENTS.md has a new line. The dict tells you what to do next.
```

### v1 vs v2 path resolution (auto-detected)

`iterate` auto-detects v1 vs v2 layout by checking for
`phases/3-implement/` next to AGENTS.md.

- **v1** — `models/` at template root. `iterate("models/foo")` resolves to
  `<root>/models/foo/`.
- **v2** — `models/` under `phases/3-implement/`. `iterate("models/foo")`
  is auto-prefixed to `<root>/phases/3-implement/models/foo/` with a
  console notice. Bare `iterate("phases/3-implement/models/foo")` also
  works (no prefix).
- Anything that doesn't look like `models/<name>/` or
  `phases/3-implement/models/<name>/` raises `ValueError` — the
  ambiguity is too sharp to silently fix.

This is the guard against the Phase-3 footgun where an agent forgets to
`cd phases/3-implement/` and `iterate` creates `models/` at the wrong
level.

## Composition with `assess-candidate-model`

Iterate **calls** `assess-candidate-model` internally as step 1. The two
skills have a clean division of labour:

| Skill | Owns | Writes to |
|---|---|---|
| `assess-candidate-model` | Per-candidate diagnostic narrative | `assessment.md` |
| `iterate` | Cross-candidate registry side-effects + routing | `MODELS.md`, `TREE.json`, `EXPERIMENTS.md` |

When `iterate(model_dir)` is called, it (a) runs assess to populate a fresh
`assessment.md`, (b) reads `- residual_verdict:` from that assessment, (c)
proceeds with CV + gate + registry updates. The residual diagnosis the
routing depends on is always fresh — no stale verdict from a prior fit.

If you want the diagnostic without the registry pollution (e.g. mid-build
sanity check), call `assess-candidate-model` directly. Iterate is the entry
point only when you're ready to log the candidate.

## Pre-gates (fire before any expensive scoring)

### Idempotence smoke — predict() must be deterministic

Before scoring, iterate calls `predict()` twice on the first 3 dev segments
and asserts bit-identical output (tolerance ~1e-12 for BLAS jitter). If
they differ, raises `NonIdempotentPredictError` and refuses to log the
node. CV becomes meaningless if predict is non-deterministic — two folds
on the same segment can disagree for reasons unrelated to the model.

Common sources: unseeded `np.random`, `torch.manual_seed` not set,
module-level mutable state, accidental external I/O (network lookups,
file reads with non-deterministic ordering). Fix the source, re-run.

### Novelty gate — notes.md must declare `## What this differs from`

m3.v3 cohort failure mode: silent re-convergence on the same approach
wearing different variable names. Iterate refuses to proceed on a bundle
whose `notes.md` is missing the `## What this differs from` section.
Format expected:

```markdown
## What this differs from

- bias-corrected-v1: same per-platform bias, but my candidate also adds
  a steering-rate residual term — measures whether the cohort §3 'lag-τ
  dead-end' applies here.
- v1: I keep V1's δ₀ but replace its first-order lag with a regime-switched
  filter. Structural delta from V1.
```

The skill checks the section's *presence*, not the *truth* of the
differs-claims — that's the agent's responsibility. Behavioural-hash
verification (running predict on a canonical fixture and comparing to
existing nodes) is an extension hook; see `_behavioural_hash` in
`iterate.py`.

Raises `NotesMissingDiffersFromError` if absent. No retries — fix the
notes.md, re-run.

## The verifier gate (auto-firing, not optional)

Every candidate goes through the same battery before it gets a row in `MODELS.md`:

1. **k-fold (k=5) route-grouped CV on the dev split** → pooled yaw RMSE and CTE RMSE as `mean ± std`. Route-grouped because adjacent segments from the same physical route are correlated; naive splits overestimate generalisation (cohort evidence: agent-07's asymmetric-bias fit flipped Lightning sign under 80-segment subsets — see `references/m4-cohort-findings.md` § 6).
2. **`residual-structure` verdict** — `noise_floor` (stop chasing this residual) or `structure_detected:<reason>` (autocorrelation lag, feature correlation, sign asymmetry).
3. **Diff vs parent** (the parent named in `notes.md` or in the call). If improvement < CV σ → the win is noise, gate emits `warn: signal-below-noise`.
4. **Diff vs V1** (always). Catches the m3.v2 failure mode of shipping a model statistically identical to V1.
5. **Fit-diagnostics propagation** — if the candidate's fit logged any of `co-collapse | stuck-on-bound | non-convergence | dev_train_gap > 30%`, the gate flags them.
6. **Test-split read is denied** by default. Test only gets scored when `pre-flight-final-model --final` runs. See `score-model` § "Test-split discipline".

The gate is a hard step. A candidate that fails the gate is *still* logged (we want to learn from failures), but its `MODELS.md` entry is tagged `status: gate-failed` with the reasons. It cannot be picked as parent for further iteration until the agent addresses the gate flags or marks the candidate `shelved`.

## Routing — what to do next

After the gate, `iterate` calls `critique-residuals` with the gate output and the residual-structure verdict, and the critique returns one of a small fixed set of routing strings:

- `keep_iterating_on_this_lever` — the residual still has structure on a feature the model already uses; refit or re-parameterize.
- `add_lever_<feature>` — the residual correlates with a feature the model isn't using yet (specific feature named).
- `drop_lever_<feature>` — a coefficient went to bound or collapsed; the lever isn't earning its place.
- `climb_to_rung_1` — the residual character is transient-dynamics-shaped (autocorrelated at short lag, correlates with `d(delta_road)/dt` and `v_mps`) and the current model can't reach it by re-fitting. Use `_shared/rung1_starter.py`.
- `try_residual_learner` — residual is high-rank but smooth in input space; ridge or GB on V1's residual likely wins (cohort evidence: agents 03, 04, 06, 08, 10 all shipped this pattern — see § 4 of cohort findings).
- `try_per_platform_bias_correction` — signed bias dominates one platform's CTE (cohort evidence: § 2). Smallest possible structural delta over V1.
- `stop_and_ship` — gate passes, residual is at noise floor, this candidate beats current leader on dev CV by > σ.

The routing is a *suggestion*, not a command. The agent is free to ignore it; the critique-residuals skill is typed-grounded (it only emits routes it can verify from the gate output) precisely so the agent treats it as a router, not a judge.

## Stagnation reset — soft-mechanical, not honor-system

If `iterate` finds the last N=3 nodes on the current branch all returned
`warn: signal-below-noise` or `keep_iterating_on_this_lever` without
crossing the noise floor, it sets `result["stagnation"] = True`, routes
`next_move = "compact_and_restart"`, and **mechanically caps the verdict
at `keep`** — a stagnant-branch node cannot be marked
`promote_to_leader`, even if its dev-CV score would otherwise qualify.
The gate reason `stagnant-branch-cannot-promote` is appended so the
agent (and pre-flight) see why.

This pairs with the pre-flight final gate (which requires the shipped
model to be `promote_to_leader`) to make the discipline mechanical for
the load-bearing case: you cannot ship a stagnant-branch model. You
*can* keep exploring inside the stagnant branch — iterate doesn't refuse
to log — but the promotion path is closed until the branch resets.

After a stagnation flag fires, the recommended reset:

1. Write a 1-page summary of *what the branch ruled out* and *what to try instead*.
2. Start a fresh Claude Code session (cold-start via `claude --workdir <root>`
   if available — see `phases/N-*/run.sh` for the pattern) seeded with only
   `EXPERIMENTS.md`, `TREE.json`, the summary, and the current leader's
   `predict.py`.

Horthy's RPI loop, sensor-triggered. Empirical: m3 cohorts past ~3
unsuccessful iterations on one branch produce silently re-convergent
attempts wearing different variable names. The verdict cap is what makes
the reset load-bearing instead of advisory.

## Modular by design

`iterate` operates on the `models/<name>/` bundle as a black box:

1. Imports `predict.py` from the bundle via `importlib`.
2. Reads `notes.md` for the model's declared rung, parent, expected residual character.
3. Runs the gate.
4. Writes back to `assessment.md`, `MODELS.md`, `TREE.json`, `EXPERIMENTS.md`.

It knows nothing about whether the model is a kinematic single-track refit, a dynamic ODE, a residual learner, or a neural network. If you build a new model class, the skill works without modification. The contract is the model bundle, not the model class.

## Output dict shape

```python
{
    "dev_cv": {
        "pooled": {"yaw_rmse": 0.0057, "yaw_std": 0.0003, "cte_rmse": 54.2, "cte_std": 1.8},
        "per_platform": {...},
    },
    "vs_parent": {"yaw_delta_pct": -1.2, "cte_delta_pct": -3.4, "signal_above_noise": True},
    "vs_v1":     {"yaw_delta_pct": -3.4, "cte_delta_pct": -6.1, "signal_above_noise": True},
    "vs_leader": {"yaw_delta_pct": -0.4, "cte_delta_pct": -1.2, "signal_above_noise": False},
    "gate": {
        "status": "warn",
        "reasons": ["fit_stuck_on_bound:tau", "dev_train_gap=22%"],
    },
    "verdict": "keep",
    "next_move": "add_lever_d_delta_dt",
    "stagnation": False,
    "tree_node_id": "n0042",
}
```

## Smoke test

`python3 _smoke.py` — builds a stub model in a tmp dir, runs `iterate`, asserts the dict has every key and `TREE.json` got a node.

## Extending this skill

The verifier gate and the routing labels are deliberately small so you can edit them. Add a route when the cohort discovers a new winning move; add a gate check when the cohort discovers a new failure mode. Same ratchet pattern as references.
