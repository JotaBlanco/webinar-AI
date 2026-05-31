# code

The project's baseline model code, symlinked into the template. Read-only.

For Module 2 / lateral-fidelity this is expected to contain at minimum:

- `ks_model.py` — the V0 kinematic-bicycle baseline. Imported by the agent as a reference; not modified.

## Setup

If this directory is empty when you clone the template, symlink the project's `code/` here:

```bash
ln -s /path/to/project/code/ks_model.py code/ks_model.py
```

The agent's `final-model/` deliverable lives at the template root (not under `code/`), so this directory stays read-only throughout the run.
