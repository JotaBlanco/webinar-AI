# code

The project's baseline model code, symlinked into the template. Read-only.

Contains `ks_model.py` (V0 kinematic-bicycle baseline) plus its sibling modules — `parameters.py`, adapters, fetchers, viz tools. `ks_model.py` imports from `parameters` directly so the whole directory must be reachable; file-level symlinking would break sibling imports.

## Setup

If this directory is empty when you clone the template, replace it with a symlink to the project's `code/` tree:

```bash
rm -rf code/                  # remove the empty stub
ln -s /path/to/project/code   # whole-dir symlink
```

The agent's `final-model/` deliverable lives at the template root (not under `code/`), so this directory stays read-only throughout the run.
