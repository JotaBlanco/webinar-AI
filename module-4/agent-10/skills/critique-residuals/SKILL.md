---
name: critique-residuals
description: Typed-grounded router — given a verifier-gate output (the dict `iterate` returns) and a residual-structure verdict, emit one of a small fixed set of routing strings telling the agent what *kind* of next move to consider. **Not a quality judge** — it only emits routes whose precondition it can verify from the inputs. The real source of truth remains the dev-CV score; this skill steers the next iteration, it does not rank candidates.
when-to-invoke: Called automatically by `iterate` after the gate runs. Also useful standalone when an agent wants to ask "given this residual character, what's the most evidence-backed next lever to try?" without re-scoring. Particularly useful before deciding whether to climb a rung — the critique is conservative about emitting `climb_to_rung_1` because rung-1 cost is real.
when-NOT-to-invoke: Do not use to rank candidates against each other (use `compare-models` or the dev-CV scores in `MODELS.md`). Do not use to decide what to ship (read `MODELS.md` and the gate output directly). Do not treat its output as authoritative — it is a router; the agent is the decider.
inputs: gate_output (dict from `iterate`), residual_verdict (str from `residual-structure`), cohort_hint (optional bool, default True — pull in the m3.v3 cohort-evidenced patterns; set False if you are running on a wholly new dataset).
outputs: dict — `route` (one of the strings below), `confidence` (`high | medium | low` — verifiability of the precondition), `rationale` (one sentence), `cohort_precedent` (citation to references/m4-cohort-findings.md if applicable).
load-cost: ~180 tokens metadata, ~320 tokens body.
---

# critique-residuals

## The route set (fixed, append-only)

The router emits exactly one of these strings. New routes get added by ratchet when the cohort discovers a new winning pattern — never inferred from first principles, never emitted speculatively.

| Route | Precondition (must be verifiable) | Cohort precedent |
|---|---|---|
| `add_route_cv_for_bias` | iterate gate emitted `bias_without_route_cv` (per-platform bias term in `coeffs.json` with no `route_cv_sigma` sibling) | §6 + §9 — m4.v1 agent-07 shipped Lightning bias selected on an i.i.d. holdout; sign was an artefact of the route split. Emitted *before* `try_per_platform_bias_correction` to force the route-CV step. |
| `try_per_platform_bias_correction` | Residual verdict = `structure_detected:signed_bias` on Mach-E or IONIQ-5 with bias magnitude > 0.0005 rad/s | §2 — agents 01, 05, 07, 09, 10 all shipped this; +3.7–4.6% CTE for ~0 structural cost |
| `try_residual_learner` | Residual verdict = `noise_floor` OR `structure_detected:feature_corr:<multiple>` AND current model is rung-0 | §4 — agents 03, 04, 06, 08, 10 shipped ridge/GB residual heads; reliably +1–5% CTE |
| `climb_to_rung_1` | Residual verdict = `structure_detected:autocorr:lag<10` AND current model is rung-0 polished AND no rung-1 candidate exists in `MODELS.md` | §1 — every cohort attempt failed; emitted with `confidence: low` and a warning to use `_shared/rung1_starter.py` + fit `C_α, Iz` instead of carParams |
| `add_lever_<feature>` | Residual verdict = `structure_detected:feature_corr:<feature>` AND `<feature>` is in the operating-contract allowlist AND model doesn't already use it | — |
| `drop_lever_<param>` | Gate reason includes `fit_stuck_on_bound:<param>` OR `fit_co_collapse:<param>` | §3 — agents 03, 05 saw lag-tau collapse; cohort evidence that lever isn't there |
| `keep_iterating_on_this_lever` | Gate status = `warn` AND signal-below-noise AND no other route's precondition is met | — |
| `stop_and_ship` | Gate status = `pass` AND beats current leader on dev CV by > σ AND residual = `noise_floor` | — |
| `compact_and_restart` | Branch has ≥3 consecutive warn/fail nodes (stagnation flag set by `iterate`) | CMU 2026 — accumulated context past ~5 turns actively interferes |
| `run_assessment_first` | Residual verdict = `unknown` (assessment.md missing — `iterate` ran on a bundle where `assess-candidate-model` hadn't populated the assessment) | — |

## Typed grounding — what makes this a router not a judge

The route's precondition is the *only* thing the skill checks. It does not assess whether the candidate "looks good" or "feels right" — those are judge tasks, prone to the 2026 self-refine "coherence trap" (model and judge share error modes; iterative self-critique amplifies confidence without adding information). By restricting routes to mechanically verifiable preconditions, the critique becomes a deterministic steering signal whose ground truth is the gate output, not LLM opinion.

When no precondition is met, the skill returns `route: keep_iterating_on_this_lever` with `confidence: low` rather than inventing a route. The agent is free to override.

## Cohort hint mode

With `cohort_hint=True` (default), the router prioritises routes with the strongest m3.v3 cohort precedent — `try_per_platform_bias_correction` and `try_residual_learner` are emitted ahead of speculative novel attacks, *if* their preconditions are met. Set `cohort_hint=False` if running on a different dataset where the m3.v3 evidence doesn't transfer.

## Output shape

```python
{
    "route": "try_residual_learner",
    "confidence": "high",
    "rationale": "Residual at noise floor on per-platform residual; current model is rung-0; cohort precedent is strong.",
    "cohort_precedent": "references/m4-cohort-findings.md §4",
}
```

## Extending this skill

When the next cohort produces a new repeating pattern, add a row to the table above with the precondition and the citation. The condition logic in `critique.py` is ~50 lines of `if` statements — deliberately small so the routing surface stays auditable.

## Cohort → route promotion ritual

A pattern earns a row in the route table only after passing through this
ritual. Don't promote routes from a single agent's success — the m3.v3
asymmetric-bias finding (§6) is what proves single-instance routes overfit.

**Promotion criteria (must satisfy all four):**

1. **Cohort recurrence** — the pattern shows up in ≥3 distinct cohort
   agents' REPORT.md `## Structures I tried` sections, with consistent
   sign (all wins or all failures).
2. **Mechanical precondition** — the trigger can be verified from the
   `iterate` gate output + `residual-structure` verdict alone. If you need
   the agent to infer "is this the right place to use it?", it's a hint,
   not a route.
3. **Cohort-findings citation** — a corresponding §N entry exists in
   `references/m4-cohort-findings.md` describing the pattern and citing
   the agent REPORTs.
4. **Reverse safety** — the route's *opposite* recommendation is also
   evidenced as wrong (so the router isn't just biased by ratchet
   asymmetry).

**The promotion edit (~10 LOC):**

1. Add a row to the route table above with the precondition + cohort
   precedent citation.
2. Add an `if residual_verdict.startswith(...)` branch in `critique.py`'s
   `critique()` function, returning the new `Route(...)` with the same
   citation in `cohort_precedent`.
3. Bump the doc's `updated:` date in frontmatter.
4. Open a PR titled `route: promote <route_name> from <§N>`.

**The deprecation ritual** (when a route ages out — pattern no longer
recurs in cohorts, or its precondition becomes verifiable elsewhere):

1. Mark the row `[deprecated as of cohort YYYY-MM-DD]` — don't delete.
2. Keep the `critique.py` branch in place but log to stderr when it fires.
3. Remove after two cohorts of zero emissions.

This ratchet is *separate* from the `m4-cohort-findings.md` ratchet
(which records cohort patterns) and from m5's
`crystallise-cohort-findings` skill (which automates the cohort-findings
edit). m5 may eventually automate the *findings* but the *route promotion*
should stay manual until the cohort cadence is high enough to make
automation safer than judgement.
