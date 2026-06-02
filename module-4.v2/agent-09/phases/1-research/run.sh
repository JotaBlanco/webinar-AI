#!/usr/bin/env bash
# Phase 1 — Research. Cold-starts a fresh Claude Code session via the
# `claude` CLI when available, falls back to printed honor-system
# instructions when not.
#
# The fresh-context property is the whole point of RPI — locking the
# artifact protects it from later phases, but only spawning a new session
# resets the context window. We try to spawn; we never just pretend to.
#
# Usage:
#   bash phases/1-research/run.sh             # cold-start if claude CLI available
#   bash phases/1-research/run.sh --manual    # skip CLI spawn, print instructions only
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PHASE="$ROOT/phases/1-research"
ART="$PHASE/artifacts"
mkdir -p "$ART"

MANUAL=0
[ "${1:-}" = "--manual" ] && MANUAL=1

if [ -f "$ART/RESEARCH.md" ] && [ ! -w "$ART/RESEARCH.md" ]; then
    echo "RESEARCH.md already locked. Phase 1 complete. Run phases/2-plan/run.sh next." >&2
    exit 1
fi
if [ -f "$ART/RESEARCH.md" ]; then
    echo "RESEARCH.md exists but is not locked. Either remove it or lock and proceed:" >&2
    echo "  bash $ROOT/lock.sh $ART/RESEARCH.md" >&2
    exit 1
fi

# Seed the artifact skeleton.
cat > "$ART/RESEARCH.md" <<'TEMPLATE'
# RESEARCH.md — Phase 1 output

**Locked after phase 1 completes.** Do not edit in later phases.

## V1 residual diagnosis (per platform)

| platform | yaw RMSE | yaw signed bias | CTE RMSE | CTE drift | residual character |
|---|---|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | | | | | |
| FORD_MUSTANG_MACH_E_MK1 | | | | | |
| HYUNDAI_IONIQ_5 | | | | | |
| TESLA_MODEL_3 | n/a | n/a | n/a | n/a | no truth — V0 passthrough |

## Candidates considered (≥5, ≥3 structurally distinct from V1)

For each candidate: name, rung tag (or `orthogonal`), residual it attacks,
cost annotation (skills/starters/references needed), expected dev-CV magnitude,
cohort precedent (`m4-cohort-findings.md §N`) if applicable.

1. **<name>** — rung `0|1|2|3|orthogonal`
   - Attacks:
   - Cost:
   - Expected dev-CV:
   - Cohort precedent:

2.

3.

4.

5.

## References cited

<!--
LIST references you cited above by filename. Phase 2 may only re-load
references that appear in this list. This forces deliberate Phase 1
citation; if you skip the list, Phase 2 has no recovery path.
-->

- references/m4-cohort-findings.md
-

## Cohort evidence to factor in

- §<N>:

## What this phase did NOT decide

- Which to implement (Phase 2)
- Which to ship (Phase 3)
- Any code (Phase 3)
TEMPLATE

# Try to spawn a fresh session. The CLI provides the cold-start that lock.sh
# alone does not.
if [ "$MANUAL" -eq 0 ] && command -v claude >/dev/null 2>&1; then
    echo "→ Phase 1 — Research"
    echo "→ Spawning fresh Claude Code session via 'claude' CLI…"
    echo "   Workdir: $ROOT"
    echo "   Seed:    $PHASE/PROMPT.md"
    echo "   Artifact target: $ART/RESEARCH.md"
    echo
    # --add-dir bounds the agent to the template root. --append-system-prompt
    # injects the phase PROMPT.md as additional system context. The session is
    # interactive so the human can review before the agent locks.
    exec claude \
        --add-dir "$ROOT" \
        --append-system-prompt "$(cat "$PHASE/PROMPT.md")"
fi

# Fallback path — honor-system. The README is explicit about what this means.
cat <<EOF
→ Phase 1 — Research (manual / honor-system fallback)

The 'claude' CLI was not invoked (either missing from PATH or --manual was
used). The cold-start guarantee is now honor-system: YOU are responsible
for opening a NEW Claude Code session — do not continue in the current one.

Open a fresh Claude Code session in: $ROOT
Seed it with the prompt at:           $PHASE/PROMPT.md
Artifact target:                      $ART/RESEARCH.md

The session must:
1. Read phases/1-research/README.md FIRST (it is your guide for this phase).
2. Read AGENTS.md (root) only for the operating contract reminder.
3. Run skills/score-model on V1 + skills/residual-structure on V1.
4. Fill the template at $ART/RESEARCH.md (≥5 candidates, cohort §-citations,
   References-cited list populated).
5. NO CODE. NO models/ directories.

When done:
  bash $ROOT/lock.sh $ART/RESEARCH.md

Next phase:
  bash $PHASE/../2-plan/run.sh
EOF
