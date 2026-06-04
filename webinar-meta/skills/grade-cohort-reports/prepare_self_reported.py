#!/usr/bin/env python3
"""Self-reported extraction prep — iter 3 diagnostic, opt-in only.

For each agent that has a REPORT.{md,txt}, render a tight per-agent extraction
prompt and emit `self-reported/invocations.json` with one Agent() call per agent.

The parent assistant must then:
    1. Read self-reported/invocations.json
    2. Fire each Agent() call in parallel (run_in_background=true)
    3. Each subagent writes its JSON to self-reported/<agent_id>.json
    4. Run `orchestrate.py finalize --grade-dir <dir>` to re-aggregate + re-render
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))
from canonical_eval import derive_agent_id_and_family  # noqa: E402


def find_report(agent_folder: Path) -> Path | None:
    for name in ("REPORT.md", "REPORT.txt"):
        p = agent_folder / name
        if p.is_file():
            return p
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--grade-dir", type=Path, required=True,
                   help="The same out-dir used by canonical_eval.py (has canonical/agent-folders.json)")
    args = p.parse_args()

    af_file = args.grade_dir / "canonical" / "agent-folders.json"
    if not af_file.is_file():
        sys.exit(f"prepare_self_reported: missing {af_file} — run canonical_eval.py first")
    agent_folders = json.loads(af_file.read_text())

    sr_dir = args.grade_dir / "self-reported"
    sr_dir.mkdir(exist_ok=True)

    template = (SKILL_DIR / "self-reported-template.md").read_text()
    parts = template.split("---", 2)
    body = parts[2] if len(parts) >= 3 else template

    invocations: list[dict] = []
    skipped: list[str] = []
    for agent_id, meta in sorted(agent_folders.items()):
        folder = Path(meta["folder"])
        report_path = find_report(folder)
        if report_path is None:
            skipped.append(agent_id)
            continue
        report_body = report_path.read_text(errors="replace")
        output_path = sr_dir / f"{agent_id}.json"
        prompt = (body
                  .replace("{{agent_id}}", agent_id)
                  .replace("{{report_path}}", str(report_path))
                  .replace("{{report_body}}", report_body)
                  .replace("{{output_path}}", str(output_path)))
        prompt_file = sr_dir / f"prompt-{agent_id}.md"
        prompt_file.write_text(prompt)
        invocations.append({
            "subagent_type": "general-purpose",
            "description":   f"extract self-reported {agent_id}",
            "run_in_background": True,
            "agent_id":      agent_id,
            "report_path":   str(report_path),
            "output_path":   str(output_path),
            "prompt":        prompt,
        })

    inv_file = sr_dir / "invocations.json"
    inv_file.write_text(json.dumps(invocations, indent=2))

    print(f"prepare_self_reported: {len(invocations)} agent(s) with a report -> {sr_dir}")
    if skipped:
        print(f"prepare_self_reported: {len(skipped)} agent(s) skipped (no REPORT.{{md,txt}}): {', '.join(skipped[:5])}{'…' if len(skipped) > 5 else ''}")
    payload = [{"subagent_type": inv["subagent_type"],
                "description": inv["description"],
                "run_in_background": inv["run_in_background"],
                "agent_id": inv["agent_id"],
                "prompt": inv["prompt"]}
               for inv in invocations]
    print()
    print("BEGIN_SELF_REPORTED_INVOCATIONS")
    print(json.dumps(payload))
    print("END_SELF_REPORTED_INVOCATIONS")
    print()
    print(f"Next: parent fires all {len(payload)} Agent() calls in ONE message (run_in_background=true).")
    print(f"      Each subagent writes its JSON to {sr_dir}/<agent_id>.json.")
    print(f"      Then: python3 orchestrate.py finalize --grade-dir {args.grade_dir}")


if __name__ == "__main__":
    main()
