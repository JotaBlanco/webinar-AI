# references

Domain documents the agent loads *on demand* — schemas, glossaries, standards, papers, drawings, vendor docs. Not loaded into AGENTS.md (that would pay tokens every turn for content the agent rarely needs).

## Access pattern

The right pattern is a **reference-style skill** that points the agent here. The skill's metadata says "use this when you need to know X"; its body is a short instruction that tells the agent which file in `references/` to read.

Example for a vehicle-dynamics project:

```
skills/vehicle-dynamics-schema/SKILL.md   # metadata + instruction
references/rlog-schema.md                  # the actual schema lookup
references/conventions.md                  # sign conventions, units, etc.
```

The skill body is 5 lines: "to look up an rlog field, read references/rlog-schema.md and find the matching row". The agent loads the schema doc only when it actually needs it (NC-12 — progressive disclosure).

## What goes here

- Schemas / data dictionaries.
- Glossaries / terminology.
- Domain standards the agent should cite or follow.
- Vendor / instrument manuals (if small enough; otherwise a pointer).
- Past project debriefs the agent should consult.

## What does NOT go here

- Tutorials / how-tos for *humans* — those go in a separate `docs/` folder if you need one. `references/` is for the agent's lookups, not your team's onboarding.
- Anything large enough to pay a meaningful per-turn token cost when loaded — those should be summarised first, then the full version put in `data/` and accessed via a tool.

## Template state

Empty. Add your domain references as you need them.
