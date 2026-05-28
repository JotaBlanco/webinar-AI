#!/usr/bin/env bash
# Reset the root substrate to angle 01's M1 (empty-lamp) start state.
# Safe to run on a throwaway branch — restore with `git checkout AGENTS.md skills`.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

# Back up workshop-end skills
if [[ -d skills && ! -d skills.workshop-end-reference ]]; then
  mv skills skills.workshop-end-reference
  mkdir skills
fi

# Truncate AGENTS.md to a minimal 3-line stub
cat > AGENTS.md <<'EOF'
# AGENTS.md
build: uv sync
lint: uv run ruff check
EOF

echo "Reset to angle 01 M1 state."
echo "Restore with: git checkout AGENTS.md && rm -rf skills && mv skills.workshop-end-reference skills"
