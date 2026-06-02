---
title: webinar-00-template-m3.v3 — Module 3 v3 substrate (V1-as-baseline, models-as-first-class)
summary: Module-3 v3 template for the lateral-fidelity webinar. The m3.v2 cohort converged hard on the recipe shipped in references/anti-patterns.md (6 of 10 shipped identical coefficients). m3.v3 pre-ships that recipe as `code/v1_baseline.py` (the new floor), strips the recipe and coefficients from the references, and reframes the agent task as building structurally-different candidate models that attack V1's residual. Adds: a `models/<name>/` directory pattern with notes.md/assessment.md, a `MODELS.md` registry, a new `assess-candidate-model` skill, and three new preflight gates (alternatives-considered header, models-registry ≥3 entries, structural-novelty diff against V1).
tags: [template, webinar, m3.v3, skills, references, lateral-fidelity]
updated: 2026-06-01
---

# webinar-00-template-m3.v3

Module 3 v3 substrate for the lateral-fidelity webinar. **The m3.v3 increment over m3.v2 is V1 as a pre-shipped baseline.** Everything else in the template — the operating contract, the schema-aware skills, the EXPERIMENTS.md log discipline — is inherited.

This README is for the human setting up the template. The agent reads [AGENTS.md](AGENTS.md) — that's the authoritative source.

## Why m3.v3 exists

The m3.v2 cohort (10/10 ok at `_grade/20260601-120739/`) demonstrated that *given the recipe*, agents converge to within 0.3 percentage points of CTE. Six of ten agents shipped V1's coefficients to three decimal places. That's good convergence — but it measured execution fidelity, not problem-solving, because `references/anti-patterns.md` shipped a complete copy-pasteable `predict()` with literal fitted coefficients alongside the diagnostic that named them as the winning move.

m3.v3's hypothesis: **moving the floor up to V1 and removing the recipe forces agents into structurally different solutions.** The cohort wants evidence on whether rung-1 dynamic single-track, residual learners, regime-switching, complementary filters, or other shapes can beat V1 — and that evidence only arrives if rung-0 refitting is no longer the obvious win.

## What's changed vs m3.v2

| change | what / where |
|---|---|
| V1 baseline pre-shipped | `code/v1_baseline.py` exports `predict_v1` and `PLATFORM_PARAMS_V1`. The m3.v2 winning recipe verbatim. |
| Recipe stripped from references | `references/anti-patterns.md` § "The legal cousin" loses its `PLATFORM_PARAMS` dict and 30-line `predict()` worked example. Concept stays as a one-paragraph note. |
| `approach-menu.md` deleted | Pre-classifying the option space anchored agents. They generate their own option list now (gated by preflight, see below). |
| `ceiling-moves.md` deleted | Pre-naming the moves above the ceiling did the same anchoring job. |
| Rung-1 scaffold removed | `references/dynamics-formulations.md` keeps the equations, parameter list, and identifiability notes. The 30-line code scaffold is gone — every agent copied it and hit the same Euler instability, producing eight indistinguishable failure reports. |
| AGENTS.md rewritten | New § "V1's residual diagnosis" ships the *diagnostic*, not the *fix*. New § "Models as first-class objects" describes the `models/<name>/` workflow. The "highest-leverage move" framing is gone. |
| `MODELS.md` registry | New top-level artifact. Each candidate model gets a `##` entry: directory, structure tag, status, dev score, verdict. |
| `models/<name>/` directory pattern | Each candidate lives in its own dir with `predict.py`, `notes.md` (formulation before code), `assessment.md` (populated by the new skill). |
| New skill: `assess-candidate-model` | Coordinator that runs score-vs-V1, compare-against-V1, residual-structure on a candidate and writes a populated `assessment.md`. |
| Preflight: three new gates | (a) `EXPERIMENTS.md` opens with ≥5-alternatives header (≥3 structurally distinct from V1); (b) `MODELS.md` has ≥3 candidates (≥1 tagged `differs-from-v1`); (c) shipped predict differs from V1 by > tolerance on a sample segment (warn-only). |
| Rung-climb gate removed | Replaced by the stronger upstream "alternatives header" and "MODELS.md ≥3" gates. `Rung:` tagging is optional on log entries. |

## What's *not* changed

- The skills toolkit (score-model, fit-model, compare-models, inspect-residuals, residual-structure, route-bias, visualise-segment, make-train-dev-split, load-segments, pre-flight-final-model) — unchanged except for preflight's new gates.
- The operating contract (8 allowlist columns, `data/sim-only/` for agent-facing scoring).
- `_shared/` math helpers.
- `references/two-kpi-tradeoff.md` and `references/exploration-discipline.md` (updated wording but same role).

## Working layout

- `code/v1_baseline.py` — the V1 baseline + its fitted coefficients. Read-only.
- `AGENTS.md` — agent-facing brief.
- `EXPERIMENTS.md` — append-only log; opens with "Alternatives considered".
- `MODELS.md` — registry of candidate models.
- `models/<name>/` — one dir per candidate (created by the agent).
- `references/` — four reference docs (anti-patterns, dynamics-formulations, exploration-discipline, two-kpi-tradeoff).
- `skills/` — ten skills inherited from m3.v2 + `assess-candidate-model` new in m3.v3.
- `final-model/` — shipped bundle, validated by `pre-flighting-final-model`.

## How to drive m3.v3 with this template

1. Each agent dir has `data/` → `../../data` and `code/` → `../../code` symlinks.
2. Open the agent dir in Claude Code. `AGENTS.md` loads.
3. Agent's task prompt names the two KPIs.
4. Inner loop: score V1 → diagnose residual → write ≥5 alternatives → build candidate in `models/<name>/` → assess vs V1 → register in MODELS.md → repeat until ≥3 candidates → ship best (or V1 with a documented negative result).
5. Run `pre-flighting-final-model` before declaring done.

## Dependencies

- Python 3.11+
- `uv` for env management (`uv sync` after first clone)
- Claude Code
