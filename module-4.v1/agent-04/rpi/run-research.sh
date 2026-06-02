#!/usr/bin/env bash
# Phase 1 — Research. Cold-starts a fresh Claude Code session via the
# `claude` CLI when available, falls back to honor-system instructions.
# Locking the artifact protects it from later phases; spawning a new
# session is what actually resets the context window — and we try to do it.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ART="$ROOT/rpi/artifacts"
mkdir -p "$ART"

MANUAL=0
[ "${1:-}" = "--manual" ] && MANUAL=1

[ -f "$ART/RESEARCH.md" ] && [ ! -w "$ART/RESEARCH.md" ] && { echo "RESEARCH.md already locked. Phase 1 complete." >&2; exit 1; }
[ -f "$ART/RESEARCH.md" ] && { echo "RESEARCH.md exists but not locked. Lock and proceed, or remove." >&2; exit 1; }

cp "$ROOT/rpi/templates/RESEARCH.md.template" "$ART/RESEARCH.md"

if [ "$MANUAL" -eq 0 ] && command -v claude >/dev/null 2>&1; then
    echo "→ Phase 1 — Research"
    echo "→ Spawning fresh Claude Code session via 'claude' CLI…"
    echo "   Workdir: $ROOT"
    echo "   Artifact target: $ART/RESEARCH.md"
    SEED="The Research phase. Read AGENTS.md, references/m4-cohort-findings.md,
and code/v1_baseline.py. Run skills/score-model on V1 and skills/residual-structure
on V1. Fill $ART/RESEARCH.md with ≥5 candidates (≥3 structurally distinct).
Populate the '## References cited' section — Phase 2 may only re-load references
that appear there. No code, no models/. Lock with: bash $ROOT/rpi/lock.sh $ART/RESEARCH.md"
    exec claude --add-dir "$ROOT" --append-system-prompt "$SEED"
fi

cat <<EOF
→ Phase 1 — Research (manual / honor-system fallback)

The 'claude' CLI was not invoked. You are responsible for opening a NEW
Claude Code session — do not continue in the current one.

Open a fresh Claude Code session in: $ROOT

The session should:
1. Read AGENTS.md, references/m4-cohort-findings.md, code/v1_baseline.py
2. Run skills/score-model on V1, skills/residual-structure on V1
3. Open $ART/RESEARCH.md — fill the template (≥5 candidates, ≥3 structurally
   distinct, '## References cited' populated)
4. NO CODE, NO models/

When done: bash $ROOT/rpi/lock.sh $ART/RESEARCH.md
Then: bash $ROOT/rpi/run-plan.sh
EOF
