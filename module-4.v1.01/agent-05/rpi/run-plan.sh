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
not load skill bodies. No code, no models/. Pick THREE candidates by default
(m4.v1.01): (A) rung-0 refinement on V1, (B) orthogonal residual learner,
(C) structurally-different — Lightning-targeted by default, since the m4.v1
cohort showed Lightning at +21% yaw vs +55% on Mach-E/IONIQ. The
physics-catalog/ ships 8 pre-built rung-1+ models for candidate C; see
references/physics-menu.md for which attacks which residual character. Two
candidates is allowed but requires a populated '## Why only two candidates'
section. EVERY candidate needs a parent baseline declared — fill in PLAN.md's
'## Parent baseline' section (V0/V1/fresh + evidence) or lock.sh will refuse
to lock. Fill $ART/PLAN.md including 'why this rung over the alternative'
rationale per candidate. Cohort precedent peer rank:
m4-cohort-findings.md §1+§4 (rung-1 / orthogonal) and §2+§9 (Lightning gap).
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
2. Pick 3 candidates by default (m4.v1.01): (A) rung-0 refinement on V1,
   (B) orthogonal residual learner, (C) structurally-different rung-1+.
   Candidate C defaults to Lightning-targeted (m4.v1 cohort showed
   Lightning at +21% yaw vs +55% on Mach-E/IONIQ). The physics-catalog/
   has 8 pre-built rung-1+ models for candidate C — see
   references/physics-menu.md. Two candidates is allowed but requires a
   populated "## Why only two candidates" section in PLAN.md.
3. Every candidate needs a parent baseline declared — fill the "## Parent
   baseline" section in PLAN.md (V0/V1/fresh + one line of evidence) or
   lock.sh will refuse to lock.
4. Fill $ART/PLAN.md with rationale for the rung choice per candidate.

When done: bash $ROOT/rpi/lock.sh $ART/PLAN.md
Then: bash $ROOT/rpi/run-implement.sh
EOF
