#!/usr/bin/env bash
# Phase 2 — Plan. Cold-starts a fresh Claude Code session, scoped to read
# ONLY the locked RESEARCH.md and references it explicitly cited.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PHASE="$ROOT/phases/2-plan"
RESEARCH="$ROOT/phases/1-research/artifacts/RESEARCH.md"
ART="$PHASE/artifacts"
mkdir -p "$ART"

MANUAL=0
[ "${1:-}" = "--manual" ] && MANUAL=1

[ -f "$RESEARCH" ] || { echo "missing $RESEARCH — run phases/1-research/run.sh first" >&2; exit 1; }
[ -w "$RESEARCH" ] && { echo "RESEARCH.md is not locked — run $ROOT/lock.sh on it first" >&2; exit 1; }
[ -f "$ART/PLAN.md" ] && [ ! -w "$ART/PLAN.md" ] && { echo "PLAN.md already locked. Run phases/3-implement/run.sh next." >&2; exit 1; }
[ -f "$ART/PLAN.md" ] && { echo "PLAN.md exists but is not locked. Lock and proceed, or remove." >&2; exit 1; }

cat > "$ART/PLAN.md" <<'TEMPLATE'
# PLAN.md — Phase 2 output

**Locked after phase 2 completes.** Do not edit in Phase 3.

## Selected candidates — ≥2, default 2, up to 3 with rationale

The pair must be **structurally distinct**. The cohort-evidenced winning
pair on this dataset is **rung-0 refinement + orthogonal residual learner**
(see `m4-cohort-findings.md` §2 + §4). A rung-1 dynamic ST is *also*
admissible as Candidate B, but §1 + §7 evidence is that every prior attempt
failed for under-parameterization — choose it only if Phase 1's RESEARCH.md
identifies a specific residual character that a residual learner cannot
capture.

### Candidate A — rung-0 refinement on V1

- **name**: <model-dir-name>
- **rung**: 0
- **parent**: v1
- **formulation summary**:
- **levers being touched**:
- **cohort precedent**: <§N from m4-cohort-findings.md>
- **dev-CV pass criterion**:
- **estimated wall clock**:

### Candidate B — structurally different (rung 1+ OR orthogonal)

- **name**: <model-dir-name>
- **rung**: `1 | 2 | 3 | orthogonal`   ← orthogonal is a peer, not a fallback
- **parent**: v1 (or candidate A's name if B builds on A)
- **formulation summary**:
- **fit strategy** (if rung 1+): MUST fit C_αf, C_αr, Iz — see `_shared/rung1_starter.py`
- **starter to use**: `_shared/rung1_starter.py` | residual-learner template | other
- **why this rung over the alternative**: (mandatory — cite the cohort
  evidence that swayed your choice between orthogonal and rung-1+)
- **cohort precedent / warning**: <§N>
- **dev-CV pass criterion**:
- **estimated wall clock**:

## Phase 3 instructions

1. Build both candidates as `phases/3-implement/models/<A>/predict.py` and
   `<B>/predict.py`.
2. Each needs a `notes.md` declaring its rung, parent, expected residual
   character, AND a `## What this differs from` section (the iterate gate
   refuses bundles missing this).
3. Run `skills/iterate` on each. The gate determines which (if any) goes to
   `final-model/`.
4. If both lose to V1 on dev CV, ship V1 with REPORT.md documenting why.

## What was deliberately excluded from the plan

- <candidate from RESEARCH.md you considered but rejected>: <one-sentence reason>
- <another>: <reason>

## Locking

After this PLAN.md is filled in:

```
bash lock.sh phases/2-plan/artifacts/PLAN.md
```

Preflight verifies PLAN.md is non-writable before the bundle can ship.
TEMPLATE

if [ "$MANUAL" -eq 0 ] && command -v claude >/dev/null 2>&1; then
    echo "→ Phase 2 — Plan"
    echo "→ Spawning fresh Claude Code session via 'claude' CLI…"
    echo "   Workdir: $ROOT"
    echo "   Allowed reads: $RESEARCH (+ references cited in its 'References cited' section)"
    echo "   Artifact target: $ART/PLAN.md"
    echo
    exec claude \
        --add-dir "$ROOT" \
        --append-system-prompt "$(cat "$PHASE/PROMPT.md")"
fi

cat <<EOF
→ Phase 2 — Plan (manual / honor-system fallback)

Open a fresh Claude Code session. Seed its context with ONLY:
- $RESEARCH (the locked Phase 1 artifact)
- $PHASE/PROMPT.md (this phase's seed prompt)
- References listed in RESEARCH.md's '## References cited' section (cited-by-name only)
- skills/*/SKILL.md (metadata only — don't load bodies)

The session must:
1. Read RESEARCH.md
2. Pick 2 candidates by default (one rung-0 refinement + one structurally
   different — orthogonal OR rung-1+, peer rank). 3 only if RESEARCH.md
   justifies it; document in PLAN.md's "Why three candidates" section.
3. Fill $ART/PLAN.md naming both, with rung tags, parent, pass criteria,
   and the mandatory 'why this rung over the alternative' rationale.

When done:
  bash $ROOT/lock.sh $ART/PLAN.md

Next:
  bash $PHASE/../3-implement/run.sh
EOF
