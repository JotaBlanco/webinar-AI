# Phase 3 — Implement — seed prompt

Paste this into a fresh Claude Code session at the template root.

---

You are entering **Phase 3 (Implement)** of an RPI-first m4 template.

Before doing anything else, read:

1. `phases/3-implement/README.md` — your guide. The full inner-loop recipe
   lives here, not in the root AGENTS.md.
2. `phases/2-plan/artifacts/PLAN.md` — the locked Phase 2 artifact.
   This names the candidates you build (2 by default, up to 3 if PLAN.md
   has a `## Why three candidates` section).

Your outputs:
- `phases/3-implement/models/<A>/` and `phases/3-implement/models/<B>/`
  candidate bundles.
- `final-model/predict.py` (the dev-CV winner)
- `REPORT.md` at the template root.
- (auto-filled by skills/iterate) `MODELS.md`, `TREE.json`,
  `EXPERIMENTS.md` at the template root.

**Scope hard limits for this session:**
- Read only what the phase README names. Don't browse `references/`; load
  named files only when PLAN.md cites them.
- Use `skills/iterate/` as the only path that writes to the registries.
- Test split (`data/sim-only/test/`, `data/sim/test/`) is denied except via
  `pre-flight-final-model --final`. Don't try to bypass.
- If iterate returns `stagnation: True`, **compact and start a fresh
  session** seeded only with EXPERIMENTS.md + TREE.json + leader predict +
  PLAN.md. The phase README has the recipe.

**Path note:** candidate `models/<name>/` directories live under
`phases/3-implement/models/` in v2 (not at root). `skills/iterate/`
auto-detects v2 and prefixes bare `models/<name>` paths — you'll see a
`[iterate] v2 layout detected; auto-prefixing...` notice when this fires.
You can also pass an explicit `model_dir=phases/3-implement/models/<name>`.

## EXIT RITUAL — DO NOT SKIP

When all candidates are scored and the dev-CV leader is copied to
`final-model/`, run **both** commands, in order:

```
python -m skills.pre_flight_final_model --final   # READS THE FROZEN TEST SPLIT
                                                  # (only allowed call to test)
                                                  # Reports dev/test gap — must
                                                  # be within band.
# Then fill REPORT.md from REPORT.md.template — the prompts feed the next
# cohort's findings ratchet.
```

If preflight reports any failure, fix and re-run. Don't ship a bundle that
doesn't pass.
