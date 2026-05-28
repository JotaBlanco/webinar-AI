# data

Raw and processed data the agent reads as input. The agent almost never reads files here directly — it goes through `tools/` (or an MCP server in `.mcp/`) so that token cost stays attributable and large files don't blow up the context window.

## Convention

```
data/
├── raw/         # untouched source data — telemetry dumps, scans, lab measurements
├── processed/   # cleaned / resampled / joined versions — derived from raw/, reproducible
└── fixtures/    # small, version-controlled subset used for demos and evals
```

## Rules of thumb

- **`raw/` is read-only**, even for the team. Never edit raw data in place; produce `processed/` outputs from it.
- **`processed/` should be reproducible** — a `code/` script or a `tools/` invocation should regenerate it from `raw/`. Don't commit anything in `processed/` whose lineage you can't reproduce.
- **`fixtures/` is for the workshop and tests** — small enough to live in git, large enough to be representative. The hello-world `example.csv` is the prototype.
- **Big data lives elsewhere** — if `raw/` would push the repo above ~100 MB, store it outside the repo and put a `raw/README.md` here pointing to the canonical location (e.g. a sibling KB folder or an S3 path).

## Template state

- `example.csv` lives at the data/ root (not under `fixtures/`) for the hello-world smoke test. Move it (or delete it) once your first real data fixture is in place.
