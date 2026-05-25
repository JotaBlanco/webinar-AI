#!/usr/bin/env bash
# Reset the root substrate to angle 04's M1 (normal AGENTS, empty skills) state.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

# Hide the workshop-end skills so the audience sees an empty folder.
if [[ -d skills && ! -d skills.workshop-end-reference ]]; then
  mv skills skills.workshop-end-reference
  mkdir skills
fi

echo "Reset to angle 04 M1 state."
echo "The workshop-end skills are in skills.workshop-end-reference/ for reference."
echo "Restore with: rm -rf skills && mv skills.workshop-end-reference skills"
