# _stage

Angle-specific tooling. One subfolder per supported workshop angle (01, 02, 04, 05). Each subfolder has:

- a `README.md` explaining how to drive the root substrate for that angle's narrative
- a `reset.sh` that mutates the root substrate into the M1 starting state for that angle
- any angle-specific stage props (the context-window inspector for 02; the four scaffolds for 05; the pre-baked second skill for 04)

## Reset mechanism

The root substrate (`../AGENTS.md`, `../skills/`) lives in its **workshop-end** state. Each angle's `reset.sh` truncates / refactors / hides files to produce that angle's M1 starting state.

Reset is reversible via `git checkout` of the root substrate paths — never lose the canonical end state. Always work on a throwaway branch when running an angle's reset:

```sh
git checkout -b rehearsal/angle-NN
bash _stage/NN-name/reset.sh
# rehearse / record
git checkout main   # restores end state
git branch -D rehearsal/angle-NN
```

## Which angle uses what

| Angle | Reset state | Stage prop | Pre-baked artifacts |
|-------|-------------|------------|---------------------|
| 01 accretion | empty AGENTS.md, empty `skills/` | inspector in corner (borrow from 02) | none — substrate grows live |
| 02 empathy | bloated AGENTS.md, 2 pre-authored skills | inspector as centrepiece | bloated AGENTS.md block to refactor |
| 04 author | normal AGENTS.md, empty `skills/` | inspector peripheral | second skill pre-baked off-stage |
| 05 experiment | normal end-state | inspector as attribution instrument | the four scaffolds S1–S4 |

Angle 03 (six-component harness-as-product) is not supported here — its scaffold diverges enough to need its own repo.

## Choose your angle late

The substrate at the repo root is angle-neutral. Build out the substrate first (replace hello-world with your real skill, fill in AGENTS.md, wire your tools), validate it works, *then* pick the angle. The four `reset.sh` scripts let you switch between angles during rehearsal without rebuilding the substrate.
