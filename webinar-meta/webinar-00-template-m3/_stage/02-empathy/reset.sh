#!/usr/bin/env bash
# Reset the root substrate to angle 02's M1 (bloated-AGENTS, hidden procedural skills) state.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

# Append the bloated block to AGENTS.md (back up first)
if [[ ! -f AGENTS.workshop-end.md ]]; then
  cp AGENTS.md AGENTS.workshop-end.md
fi
cat "$STAGE_DIR/bloated-agents-md.md" >> AGENTS.md

# Hide procedural skills (keep reference-style skills visible).
# TODO: customise this — depends on which of your skills are procedural vs reference.
# As a default, hide everything except any skill whose folder name starts with "ref-" or "schema-".
for d in skills/*/; do
  name="$(basename "$d")"
  if [[ "$name" =~ ^(ref-|schema-) ]]; then
    continue
  fi
  mv "$d" "skills/.hidden_${name}"
done

echo "Reset to angle 02 M1 state."
echo "Restore with: git checkout AGENTS.md && rm AGENTS.workshop-end.md && for d in skills/.hidden_*; do mv \"\$d\" \"skills/\${d#skills/.hidden_}\"; done"
