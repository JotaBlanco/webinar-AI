#!/usr/bin/env python3
"""Single entry point for the grade-cohort-reports skill.

Default mode runs the full canonical pipeline end-to-end, no LLM, no parent
hand-firing of subagents:

    python3 orchestrate.py grade \\
        --idea-id idea-01-lateral-attribution \\
        --agent-folders "module-*/agent-*/final-model" [more globs...]
        [--out-dir _grade/<ts>]
        [--concurrency N]
        [--timeout-per-agent SECONDS]
        [--rebuild-baseline]
        [--with-self-reported]            # iteration 3 — opt-in diagnostic

Sub-commands for power users:
    baseline   — just (re)build the cached V0 baseline
    eval       — only run canonical_eval (skip aggregate + report)
    aggregate  — only re-aggregate from existing canonical/*.json
    report     — only re-render cohort.md from cohort.json
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
BASELINE = SKILL_DIR / "baseline.py"
CANONICAL = SKILL_DIR / "canonical_eval.py"
AGGREGATE = SKILL_DIR / "aggregate.py"
REPORT = SKILL_DIR / "report.py"
REPORT_HTML = SKILL_DIR / "report_html.py"
REPORT_PDF = SKILL_DIR / "report_pdf.py"
PREPARE_SR = SKILL_DIR / "prepare_self_reported.py"

# Venv inside the skill — contains plotly, weasyprint, kaleido, pandas, numpy.
# Used for the chart/HTML/PDF renderers. Falls back to system python3 if absent.
VENV_PY = SKILL_DIR / ".venv" / "bin" / "python3"


def _python() -> str:
    return str(VENV_PY) if VENV_PY.is_file() else "python3"


def _run(script: Path, *args: str, use_venv: bool = False) -> int:
    py = _python() if use_venv else "python3"
    return subprocess.call([py, str(script), *args])


def cmd_grade(rest: list[str]) -> int:
    p = argparse.ArgumentParser(prog="orchestrate.py grade")
    p.add_argument("--idea-id", required=True)
    p.add_argument("--agent-folders", required=True, nargs="+")
    p.add_argument("--out-dir", type=Path, default=None)
    p.add_argument("--concurrency", type=int, default=0)
    p.add_argument("--timeout-per-agent", type=int, default=120)
    p.add_argument("--rebuild-baseline", action="store_true")
    p.add_argument("--with-self-reported", action="store_true",
                   help="ALSO run the self-reported diagnostic pass (iter 3, not yet wired)")
    args = p.parse_args(rest)

    # 1) canonical_eval handles baseline build + per-agent eval. out-dir is auto-stamped if not given.
    eval_args = ["--idea-id", args.idea_id, "--agent-folders", *args.agent_folders]
    if args.out_dir:
        eval_args += ["--out-dir", str(args.out_dir)]
    if args.concurrency:
        eval_args += ["--concurrency", str(args.concurrency)]
    eval_args += ["--timeout-per-agent", str(args.timeout_per_agent)]
    if args.rebuild_baseline:
        eval_args.append("--rebuild-baseline")
    rc = _run(CANONICAL, *eval_args)
    if rc != 0:
        return rc

    # Find the out-dir canonical_eval picked.
    if args.out_dir is None:
        # canonical_eval prints the path; here we just glob for the newest _grade/<ts>/canonical.
        candidates = sorted(
            (p for p in (Path.cwd() / "_grade").glob("*") if p.is_dir() and (p / "canonical").is_dir()),
            reverse=True,
        )
        if not candidates:
            print("orchestrate: cannot locate fresh out-dir under _grade/", file=sys.stderr)
            return 2
        out_dir = candidates[0]
    else:
        out_dir = args.out_dir

    # 2) optional self-reported diagnostic (iter 3)
    sr_invocations = None
    if args.with_self_reported:
        rc = _run(PREPARE_SR, "--grade-dir", str(out_dir))
        if rc != 0:
            return rc
        sr_invocations = out_dir / "self-reported" / "invocations.json"

    # 3) aggregate
    rc = _run(AGGREGATE, "--grade-dir", str(out_dir))
    if rc != 0:
        return rc

    # 4) render markdown report (iter 1)
    rc = _run(REPORT, "--grade-dir", str(out_dir))
    if rc != 0:
        return rc

    # 5) render HTML + PDF (iter 2). Requires the skill's venv.
    if not VENV_PY.is_file():
        print("orchestrate: WARN — skill venv not found at .venv/, skipping HTML+PDF.")
        print(f"            create it with: cd {SKILL_DIR} && python3 -m venv .venv && "
              f".venv/bin/pip install plotly kaleido weasyprint pandas numpy")
        return 0
    rc = _run(REPORT_HTML, "--grade-dir", str(out_dir), use_venv=True)
    if rc != 0:
        return rc
    rc = _run(REPORT_PDF, "--grade-dir", str(out_dir), use_venv=True)
    if rc != 0:
        return rc

    # If self-reported is requested, leave a clear instruction to the operator.
    if sr_invocations and sr_invocations.is_file():
        print()
        print("=" * 70)
        print("SELF-REPORTED EXTRACTION READY")
        print("=" * 70)
        print(f"Invocations written to: {sr_invocations}")
        print(f"Next: parent fires each Agent() call in parallel, then runs:")
        print(f"      python3 orchestrate.py finalize --grade-dir {out_dir}")

    return 0


def cmd_finalize(rest: list[str]) -> int:
    """Re-aggregate + re-render after self-reported subagents have finished."""
    p = argparse.ArgumentParser(prog="orchestrate.py finalize")
    p.add_argument("--grade-dir", type=Path, required=True)
    args = p.parse_args(rest)
    rc = _run(AGGREGATE, "--grade-dir", str(args.grade_dir))
    if rc != 0:
        return rc
    rc = _run(REPORT, "--grade-dir", str(args.grade_dir))
    if rc != 0:
        return rc
    if not VENV_PY.is_file():
        print("orchestrate finalize: skill venv missing, skipping HTML/PDF.")
        return 0
    rc = _run(REPORT_HTML, "--grade-dir", str(args.grade_dir), use_venv=True)
    if rc != 0:
        return rc
    return _run(REPORT_PDF, "--grade-dir", str(args.grade_dir), use_venv=True)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    mode = sys.argv[1]
    rest = sys.argv[2:]
    if mode == "grade":
        sys.exit(cmd_grade(rest))
    elif mode == "finalize":
        sys.exit(cmd_finalize(rest))
    elif mode == "baseline":
        sys.exit(_run(BASELINE, *rest))
    elif mode == "eval":
        sys.exit(_run(CANONICAL, *rest))
    elif mode == "aggregate":
        sys.exit(_run(AGGREGATE, *rest))
    elif mode == "report":
        sys.exit(_run(REPORT, *rest))
    elif mode == "report-html":
        sys.exit(_run(REPORT_HTML, *rest, use_venv=True))
    elif mode == "report-pdf":
        sys.exit(_run(REPORT_PDF, *rest, use_venv=True))
    else:
        sys.exit(f"orchestrate: unknown mode '{mode}' "
                 f"(use 'grade', 'baseline', 'eval', 'aggregate', or 'report')")


if __name__ == "__main__":
    main()
