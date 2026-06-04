#!/usr/bin/env bash
# Phase 3 — Implement. Cold-starts a fresh Claude Code session; reads only
# the locked PLAN.md and the skills/starters the plan names.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ART="$ROOT/rpi/artifacts"

MANUAL=0
[ "${1:-}" = "--manual" ] && MANUAL=1

[ -f "$ART/PLAN.md" ] || { echo "missing PLAN.md — run rpi/run-plan.sh first" >&2; exit 1; }
[ -w "$ART/PLAN.md" ] && { echo "PLAN.md is not locked — run rpi/lock.sh on it first" >&2; exit 1; }

if [ "$MANUAL" -eq 0 ] && command -v claude >/dev/null 2>&1; then
    echo "→ Phase 3 — Implement"
    echo "→ Spawning fresh Claude Code session via 'claude' CLI…"
    SEED="The Implement phase. Read ONLY $ART/PLAN.md, skills/iterate/SKILL.md,
skills/score-model/SKILL.md, skills/critique-residuals/SKILL.md,
_shared/rung1_starter.py (if plan names rung-1), and code/v1_baseline.py.
Build both candidate model bundles named in PLAN.md under models/<name>/.
Each needs notes.md with a '## What this differs from' section (iterate
refuses bundles missing it). Run skills/iterate on each. Pick dev-CV
winner. Ship to final-model/. Run pre-flight-final-model --final."
    exec claude --add-dir "$ROOT" --append-system-prompt "$SEED"
fi

cat <<EOF
→ Phase 3 — Implement (manual / honor-system fallback)

Open a fresh Claude Code session. Seed context with ONLY:
- $ART/PLAN.md
- skills/iterate/SKILL.md + skills/score-model/SKILL.md + critique-residuals + visualise-tree
- _shared/rung1_starter.py (if PLAN names rung-1)
- code/v1_baseline.py

The session should:
1. Build BOTH candidate bundles named in PLAN.md. Each needs notes.md with
   a '## What this differs from' section (iterate refuses bundles missing it).
2. Run skills/iterate on each — auto-fills MODELS.md and TREE.json.
3. Optional: bash launch-rungs/launch.sh — fan out to refine the leader.
4. Pick the dev-CV winner. Copy to final-model/predict.py.
5. Run skills/pre-flight-final-model --final.

If both lose to V1, ship V1 with REPORT.md explaining why.
EOF
