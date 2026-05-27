#!/usr/bin/env python3
"""Discover cohort reports, load the rubric, render judge prompts, emit invocations.

Usage:
    python3 prepare.py \\
        --idea-id idea-01-lateral-attribution \\
        --reports "/abs/path/to/agent-*/REPORT.md" [more globs or explicit paths...] \\
        [--out-dir /abs/path/to/_grade/<timestamp>] \\
        [--manifest /abs/path/to/manifest.json]

What it produces (under <out-dir>):
    judge-<agent_id>.prompt.md   # one per report
    invocations.json             # Agent() calls for the parent to fire
    rubric-snapshot.yaml         # the rubric block at grading time (for reproducibility)

Does NOT call the Agent tool itself — emits the JSON the parent assistant should fire.
"""

import argparse
import datetime
import glob
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CHALLENGES_DIR = REPO_ROOT / "webinar-00" / "domain-knowledge-challenges"
SKILL_DIR = Path(__file__).resolve().parent


def load_rubric(idea_id: str) -> tuple[str, dict, str]:
    """Return (rubric_yaml_block_as_string, parsed_dict, full_challenge_md)."""
    candidates = [
        CHALLENGES_DIR / f"{idea_id}.md",
        CHALLENGES_DIR / f"{idea_id}",
    ]
    md_path = next((c for c in candidates if c.is_file()), None)
    if md_path is None:
        sys.exit(f"prepare: cannot find challenge file for idea-id '{idea_id}' under {CHALLENGES_DIR}")

    text = md_path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        sys.exit(f"prepare: {md_path} has no YAML frontmatter")
    yaml_block = m.group(1)

    # Minimal YAML parse — we only need success-metrics for sanity-check; the judge sees the raw block.
    # Avoid adding PyYAML dependency.
    parsed: dict = {"raw": yaml_block}
    if "success-metrics" not in yaml_block:
        sys.exit(f"prepare: {md_path} YAML has no 'success-metrics' block — cannot grade")
    return yaml_block, parsed, text


def derive_agent_id(report_path: Path) -> str:
    """raw-model/idea-01/agent-03/REPORT.md  -> agent-03
       webinar-angle-A/modulo-1/report.md    -> webinar-angle-A_modulo-1
    """
    parts = report_path.parts
    # Find the folder containing the report.
    parent = report_path.parent
    name = parent.name
    if re.fullmatch(r"agent-\d+", name):
        return name
    # angle/module case
    grandparent = parent.parent.name
    if re.fullmatch(r"webinar-angle-[A-Z0-9]+", grandparent) and re.fullmatch(r"modulo-\d+", name):
        return f"{grandparent}_{name}"
    # fallback
    return f"{parent.parent.name}_{name}"


def expand_reports(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for pat in patterns:
        # explicit path or glob — glob always works on a literal too
        matches = [Path(p).resolve(strict=False) for p in glob.glob(pat)]
        if not matches and "*" not in pat and "?" not in pat:
            sys.exit(f"prepare: report not found: {pat}")
        for p in matches:
            if p in seen:
                continue
            if not p.is_file():
                continue
            seen.add(p)
            paths.append(p)
    if not paths:
        sys.exit(f"prepare: no reports matched: {patterns}")
    return sorted(paths)


def fill_template(template: str, *, idea_id: str, rubric_yaml: str,
                  agent_id: str, report_path: Path, report_body: str) -> str:
    return (template
            .replace("{{idea_id}}", idea_id)
            .replace("{{rubric_yaml}}", rubric_yaml)
            .replace("{{agent_id}}", agent_id)
            .replace("{{report_path}}", str(report_path))
            .replace("{{report_body}}", report_body))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--idea-id", required=True,
                   help="filename stem under webinar-00/domain-knowledge-challenges/ (e.g. idea-01-lateral-attribution)")
    p.add_argument("--reports", required=True, nargs="+",
                   help="one or more report paths or globs (each glob expanded)")
    p.add_argument("--out-dir", type=Path, default=None,
                   help="where to write prompts + invocations.json (default: cwd/_grade/<ts>)")
    p.add_argument("--manifest", type=Path, default=None,
                   help="optional JSON {report_path: {key:val}} of per-report metadata; passed through to aggregate.py")
    args = p.parse_args()

    rubric_yaml, _, _ = load_rubric(args.idea_id)

    reports = expand_reports(args.reports)

    if args.out_dir is None:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        args.out_dir = Path.cwd() / "_grade" / ts
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Snapshot the rubric for reproducibility.
    (args.out_dir / "rubric-snapshot.yaml").write_text(rubric_yaml)

    template = (SKILL_DIR / "prompt-template.md").read_text()
    parts = template.split("---", 2)
    body = parts[2] if len(parts) >= 3 else template

    invocations: list[dict] = []
    for report in reports:
        agent_id = derive_agent_id(report)
        report_body = report.read_text()
        prompt = fill_template(body,
                               idea_id=args.idea_id,
                               rubric_yaml=rubric_yaml,
                               agent_id=agent_id,
                               report_path=report,
                               report_body=report_body)
        prompt_file = args.out_dir / f"judge-{agent_id}.prompt.md"
        prompt_file.write_text(prompt)
        invocations.append({
            "subagent_type": "general-purpose",
            "description": f"grade {agent_id}",
            "run_in_background": True,
            "agent_id": agent_id,
            "report_path": str(report),
            "prompt": prompt,
        })

    inv_file = args.out_dir / "invocations.json"
    inv_file.write_text(json.dumps(invocations, indent=2))

    # Persist optional manifest passthrough.
    if args.manifest is not None and args.manifest.is_file():
        (args.out_dir / "manifest.json").write_text(args.manifest.read_text())

    print(f"out_dir: {args.out_dir}")
    print(f"rubric:  webinar-00/domain-knowledge-challenges/{args.idea_id}.md")
    print(f"reports: {len(reports)}")
    for r in reports:
        print(f"  - {r}")
    print()
    payload = [{"subagent_type": inv["subagent_type"],
                "description": inv["description"],
                "run_in_background": inv["run_in_background"],
                "agent_id": inv["agent_id"],
                "prompt": inv["prompt"]}
               for inv in invocations]
    print("BEGIN_INVOCATIONS")
    print(json.dumps(payload))
    print("END_INVOCATIONS")
    print()
    print(f"Next: fire all {len(payload)} Agent() calls in ONE message (run_in_background=true).")
    print(f"      Then save each subagent's JSON response under {args.out_dir}/raw/<agent_id>.json")
    print(f"      Then: python3 aggregate.py --grade-dir {args.out_dir}")


if __name__ == "__main__":
    main()
