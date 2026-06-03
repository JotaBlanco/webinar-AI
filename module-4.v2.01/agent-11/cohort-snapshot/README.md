# cohort-snapshot/ — what the previous 10 agents did

Frozen copy (taken 2026-06-03) of every sibling agent's run artefacts in
this cohort. You can read these freely — they are inside your module subtree
and the isolation hook will allow it. The originals (`../agent-01/` …
`../agent-10/`) are outside your subtree and reading them directly will be
blocked; use this snapshot instead.

## What you'll find per agent

```
agent-NN/
├── REPORT.md            — final write-up (headline numbers, what shipped, lessons)
├── EXPERIMENTS.md       — append-only log: every candidate scored, parent, rung, verdict
├── MODELS.md            — tree-structured candidate registry
├── TREE.json            — same tree, machine-readable
└── models/<mname>/
    ├── coeffs.json      — fitted coefficients (if they fit it)
    └── scorecard.json   — dev/test scores (if they scored it)
```

## Known data-quality caveat

`agent-10/EXPERIMENTS.md`, `agent-10/MODELS.md`, and `agent-10/TREE.json`
were inadvertently reset to template-pristine state during scaffolding for
this run. **Agent-10's own REPORT.md is intact** and contains the summary;
the per-experiment trail for agent-10 specifically is lost. Treat agent-10
as "report only".

## Suggested reading order (≤20 min)

1. Loop over `agent-*/REPORT.md` — get each agent's headline number and the
   "most surprising thing" they reported. This is the 80/20 of the cohort.
2. Look at `agent-*/MODELS.md` — which models actually shipped vs which
   stayed in draft. Pay attention to status (shipped / kept / shelved).
3. Look at the per-model `scorecard.json` files to see which platforms
   benefited from each rung. Especially: did anyone beat V1 on yaw?
4. Read `agent-*/EXPERIMENTS.md` to learn the failure modes. The cohort
   shipped overwhelmingly rung-0 (V1 verbatim) — your panel needs to know
   *why* the rung-1+ climbs collapsed.

## What to feed the dream team in the first round

Distill the cohort into 1 page of facts:
- Cohort headline (best yaw, best CTE, what platform/model)
- How many shipped a rung-≥1 model
- The dominant failure mode of each prefilled physics model
  (M1, M2, M3, M4, M5)
- Per-platform asymmetry: F150 vs Mustang vs Ioniq, what's stubborn
- Train-dev gap stories (M1 collapse — does it generalise across agents?)

Then ask Vorster, Sato, and Almeida (separately, in parallel) what they
make of this and what they'd try next. Reconcile in `cohort-review/
panel-round-01.md`.
