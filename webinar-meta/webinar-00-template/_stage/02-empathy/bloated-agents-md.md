# --- BLOATED DOMAIN-CONVENTIONS BLOCK (TEMPLATE) ---
#
# This block is appended to AGENTS.md for angle 02's M1 start state. It is
# deliberately ~900 tokens of domain conventions that *should* be a skill
# (loaded on demand), but for the workshop's M1 it sits in AGENTS.md and gets
# paid for every turn. In M3, the workshop driver refactors it into
# `skills/<domain-conventions>/SKILL.md` live on stage.
#
# REPLACE the body below with your own domain's ~900 tokens of conventions.
# The exact count matters less than the visible per-turn-cost difference in
# the inspector before vs after the refactor.

## Domain conventions (TEMPLATE — replace)

### Coordinate frames / reference systems

TODO — describe your domain's coordinate frames, reference systems, datums. Should be ~2-3 paragraphs of conventions a domain expert takes for granted but a generic LLM would not know.

### Units and signs

TODO — units glossary. Every unit that has a "common mistake" version (e.g. degrees vs radians; m vs mm; psi vs bar; deg C vs K). Sign conventions for any quantity where sign matters.

### Reference signal sources / measurement conventions

TODO — what are the canonical signals / measurements / files your team works with? What is each one's source, calibration state, sampling rate, expected range?

### Time / spatial alignment

TODO — how do you align signals / measurements / models in time and space? What are the gotchas?

### Naming conventions

TODO — naming for parameters, signals, files, runs, experiments.

---

The structure above is the *shape* of any domain's bloated conventions block — coordinate frames, units, signal sources, alignment, naming. Fill in the body with your domain's specifics. Target ~900 tokens total so the per-turn-cost delta in the inspector is visible.
