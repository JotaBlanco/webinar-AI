# AGENTS.md

Runtime substrate for the sim-real correlation work. Lean by design — every line below is here because something broke when it wasn't. Domain knowledge and operational detail live in `skills/` (load on demand, do not preload).

## Project purpose

Validate vehicle dynamics models against real openpilot driving data. The thing under test is the *residual* between predicted and measured lateral response (yaw rate, lateral G). Speed-known lateral-only mode is the operating contract — see `skills/sim-real-runtime/`.

## Build / run

```bash
python code/generate_simdata_ford.py    # Mach-E + F-150 rlog → KS sim CSVs in data/sim/
python code/plot_simdata_ford.py        # render comparison PNGs
```

Dependencies pinned via `pyproject.toml`. If a script imports something missing, install it explicitly — don't add to `pyproject.toml` without asking.

## Skills inventory (metadata only — load on demand)

- `skills/vehicle-dynamics-rlog/` — conventions, units, sign rules, fidelity ladder. Load before *interpreting* signals or *modifying* the model.
- `skills/sim-real-runtime/` — workspace layout, CSV schema, operating contract (speed-known lateral-only), how to run the generators. Load when *running* code or *reading data* for the first time in a session.

## References

`references/` — raw CSV schema and per-platform parameter summaries. Load on demand from inside a skill.

## Known traps (the short list — long form lives in the relevant skill)

- ISO 8855 ≠ SAE J670 (sign of Y axis differs). The model and the CAN data are both ISO 8855 — don't reintroduce a flip.
- Tesla CSVs have no measured yaw-rate truth channel — only Ford does. Don't try to compute residuals on Tesla.
- Don't bump `code/_schema/` pins. The input contract assumes them.
