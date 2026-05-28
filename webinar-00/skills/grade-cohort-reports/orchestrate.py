#!/usr/bin/env python3
"""One-call orchestrator for the grade-cohort-reports skill.

Usage:
    # Prepare: discover reports, materialise prompts, emit Agent() invocations.
    python3 orchestrate.py grade --idea-id <id> --reports <glob/path> [more globs/paths...]
        [--out-dir DIR] [--manifest manifest.json]

    # Aggregate: after parent has persisted each judge's JSON to <grade-dir>/raw/<agent_id>.json.
    python3 orchestrate.py aggregate --grade-dir DIR

The parent assistant must:
    1) Call `orchestrate.py grade ...`
    2) Read the BEGIN_INVOCATIONS/END_INVOCATIONS JSON
    3) Fire one Agent() per entry in a SINGLE message (run_in_background=true)
    4) When each subagent returns, persist its strict-JSON output to <grade-dir>/raw/<agent_id>.json
    5) Call `orchestrate.py aggregate --grade-dir <grade-dir>`
"""

import argparse
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
PREPARE = SKILL_DIR / "prepare.py"
PREPARE_CANONICAL = SKILL_DIR / "prepare_canonical.py"
AGGREGATE = SKILL_DIR / "aggregate.py"
REPORT = SKILL_DIR / "report.py"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    mode = sys.argv[1]
    rest = sys.argv[2:]
    if mode == "grade":
        sys.exit(subprocess.call(["python3", str(PREPARE)] + rest))
    elif mode == "canonical-grade":
        sys.exit(subprocess.call(["python3", str(PREPARE_CANONICAL)] + rest))
    elif mode == "aggregate":
        sys.exit(subprocess.call(["python3", str(AGGREGATE)] + rest))
    elif mode == "report":
        sys.exit(subprocess.call(["python3", str(REPORT)] + rest))
    else:
        sys.exit(f"orchestrate: unknown mode '{mode}' (use 'grade', 'canonical-grade', 'aggregate', or 'report')")


if __name__ == "__main__":
    main()
