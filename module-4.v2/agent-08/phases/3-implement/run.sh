#!/usr/bin/env bash
# Phase 3 — Implement. Cold-starts a fresh Claude Code session for the
# implement-and-iterate work. The PLAN.md is the spec.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PHASE="$ROOT/phases/3-implement"
PLAN="$ROOT/phases/2-plan/artifacts/PLAN.md"

MANUAL=0
[ "${1:-}" = "--manual" ] && MANUAL=1

[ -f "$PLAN" ] || { echo "missing $PLAN — run phases/2-plan/run.sh first" >&2; exit 1; }
[ -w "$PLAN" ] && { echo "PLAN.md is not locked — run $ROOT/lock.sh on it first" >&2; exit 1; }

mkdir -p "$PHASE/models"

if [ "$MANUAL" -eq 0 ] && command -v claude >/dev/null 2>&1; then
    echo "→ Phase 3 — Implement"
    echo "→ Spawning fresh Claude Code session via 'claude' CLI…"
    echo "   Workdir: $ROOT"
    echo "   Spec:    $PLAN"
    echo "   Models will land under: $PHASE/models/"
    echo
    exec claude \
        --add-dir "$ROOT" \
        --append-system-prompt "$(cat "$PHASE/PROMPT.md")"
fi

cat <<EOF
→ Phase 3 — Implement (manual / honor-system fallback)

Open a fresh Claude Code session. Seed context with ONLY:
- $PLAN (the locked Phase 2 artifact)
- skills/iterate/SKILL.md + skills/score-model/SKILL.md + critique-residuals + visualise-tree
- _shared/rung1_starter.py (if PLAN names a rung-1 candidate)
- _shared/traj_metrics.py
- code/v1_baseline.py

The session must:
1. Build BOTH candidate model bundles named in PLAN.md under
   $PHASE/models/<name>/. Each needs notes.md with a
   '## What this differs from' section (iterate refuses bundles missing it).
2. Run skills/iterate on each — auto-fills MODELS.md and TREE.json at root.
3. (Optional) bash launch-rungs/launch.sh — fan out to refine the leader.
4. Pick the dev-CV winner per the gate output.
5. Copy the winner's predict.py to final-model/predict.py.
6. Run skills/pre-flight-final-model --final to confirm the deliverable
   contract AND read the frozen test split.

If both candidates lose to V1, ship V1 and write a REPORT.md explaining why.
EOF
