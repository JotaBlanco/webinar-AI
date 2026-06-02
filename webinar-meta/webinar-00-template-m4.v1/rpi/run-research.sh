#!/usr/bin/env bash
# Phase 1 — Research. Fresh context, no code, locked RESEARCH.md at exit.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ART="$ROOT/rpi/artifacts"
mkdir -p "$ART"
[ -f "$ART/RESEARCH.md" ] && { echo "RESEARCH.md already exists at $ART/. Remove or run a new session." >&2; exit 1; }

cp "$ROOT/rpi/templates/RESEARCH.md.template" "$ART/RESEARCH.md"

cat <<EOF
→ Phase 1 — Research

Start a FRESH Claude Code session in: $ROOT
Context budget: keep below 40% fill.

The session should:
1. Read AGENTS.md, references/, code/v1_baseline.py
2. Run skills/score-model on V1 to see the V1 residual per platform
3. Open $ART/RESEARCH.md (this is your output target)
4. Fill in the template — list ≥5 candidate model formulations with cost
   annotations. NO CODE. NO models/ directories.

When done: bash $ROOT/rpi/lock.sh $ART/RESEARCH.md
Then proceed to Phase 2: bash $ROOT/rpi/run-plan.sh
EOF
