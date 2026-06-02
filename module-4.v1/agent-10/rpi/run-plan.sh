#!/usr/bin/env bash
# Phase 2 — Plan. Cold-starts a fresh Claude Code session; reads only the
# locked RESEARCH.md and the references its '## References cited' section
# names by filename.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ART="$ROOT/rpi/artifacts"

MANUAL=0
[ "${1:-}" = "--manual" ] && MANUAL=1

[ -f "$ART/RESEARCH.md" ] || { echo "missing RESEARCH.md — run rpi/run-research.sh first" >&2; exit 1; }
[ -w "$ART/RESEARCH.md" ] && { echo "RESEARCH.md is not locked — run rpi/lock.sh on it first" >&2; exit 1; }
[ -f "$ART/PLAN.md" ] && [ ! -w "$ART/PLAN.md" ] && { echo "PLAN.md already locked. Run rpi/run-implement.sh next." >&2; exit 1; }
[ -f "$ART/PLAN.md" ] && { echo "PLAN.md exists but not locked." >&2; exit 1; }

cp "$ROOT/rpi/templates/PLAN.md.template" "$ART/PLAN.md"

if [ "$MANUAL" -eq 0 ] && command -v claude >/dev/null 2>&1; then
    echo "→ Phase 2 — Plan"
    echo "→ Spawning fresh Claude Code session via 'claude' CLI…"
    SEED="The Plan phase. Read ONLY $ART/RESEARCH.md and the references its
'## References cited' section names by filename. Skill metadata is fine; do
not load skill bodies. No code, no models/. Pick exactly TWO candidates:
one rung-0 refinement + one structurally-different (orthogonal residual
learner OR rung-1 — peer rank per m4-cohort-findings.md §1+§4). Fill
$ART/PLAN.md including 'why this rung over the alternative' rationale.
Lock with: bash $ROOT/rpi/lock.sh $ART/PLAN.md"
    exec claude --add-dir "$ROOT" --append-system-prompt "$SEED"
fi

cat <<EOF
→ Phase 2 — Plan (manual / honor-system fallback)

Open a fresh Claude Code session. Seed its context with ONLY:
- $ART/RESEARCH.md (the locked Phase 1 artifact)
- References named in RESEARCH.md's '## References cited' section
- skills/*/SKILL.md (metadata only)

Read NOTHING else from references/ or code/.

The session should:
1. Read RESEARCH.md
2. Pick 2 candidates by default (one rung-0 refinement + one structurally
   different — orthogonal OR rung-1+, peer rank). 3 only if RESEARCH.md
   justifies it; document in PLAN.md's "Why three candidates" section.
3. Fill $ART/PLAN.md with rationale for the rung choice

When done: bash $ROOT/rpi/lock.sh $ART/PLAN.md
Then: bash $ROOT/rpi/run-implement.sh
EOF
