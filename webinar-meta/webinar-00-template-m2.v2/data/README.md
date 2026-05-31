# data

Sim data tree for the lateral-fidelity task. Read-only. Symlinked into this template from the project's top-level `data/` directory — `git status` should not show changes here.

## Expected layout

```
data/
└── sim/
    └── segments/
        └── <PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/
            └── sim.csv
```

Every skill in `skills/` that touches data assumes this schema. Platform is the 3rd-from-rightmost directory; route is the 2nd-from-rightmost.

## Setup

If this directory is empty when you clone the template, create the symlink:

```bash
ln -s /path/to/project/data/sim data/sim
```
