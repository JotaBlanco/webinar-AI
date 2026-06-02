#!/usr/bin/env python3
"""Collect per-agent Claude token expenditure from Claude Code subagent transcripts.

Each `/launch` writes a separate JSONL transcript per spawned subagent at:
    ~/.claude/projects/<encoded-cwd>/<parent-session>/subagents/agent-*.jsonl

Where `<encoded-cwd>` is the project cwd with '/' replaced by '-' (and the leading
'/' becomes a leading '-' too).

For each transcript we:
  1. Parse the first `user` message to find the workshop working-directory line
     (a backticked absolute path containing `/agent-NN/`).
  2. Derive (agent_id, family) the same way canonical_eval does — guaranteeing
     join compatibility with cohort.json.
  3. Sum `message.usage.{input_tokens, output_tokens, cache_creation_input_tokens,
     cache_read_input_tokens}` across every `assistant` message.
  4. If the same agent_id appears in multiple transcripts (re-launches), keep the
     MOST RECENT one (by file mtime). We do not blend runs — the cohort being
     graded reflects whichever final-model is on disk now, so the matching run is
     the latest launch.

Returns a {agent_id: usage_record} mapping where usage_record has:
    input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens,
    total_tokens, n_assistant_turns, transcript_path, transcript_mtime_iso
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Reuse the canonical agent-id derivation so IDs join cleanly with cohort.json.
SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))
from canonical_eval import derive_agent_id_and_family  # noqa: E402


USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)

# Match a backticked absolute path that contains `/agent-NN/` — that's the
# working-directory line emitted by the launch template.
_WORKDIR_RE = re.compile(r"`(/[^`\n]*?/agent-\d+/?)`")


def project_transcripts_root(cwd: Path | None = None) -> Path:
    """`~/.claude/projects/<encoded-cwd>/` for the given cwd (default: process cwd).

    The Claude Code session-store encodes cwd by replacing '/' with '-' — so
    /Users/foo/bar  becomes  -Users-foo-bar  (note the leading dash from the
    leading slash).
    """
    cwd = cwd or Path.cwd()
    encoded = str(cwd).replace("/", "-")  # leading '/' -> leading '-'
    return Path("~/.claude/projects").expanduser() / encoded


def _first_user_text(jsonl_path: Path) -> str | None:
    """Return the textual body of the FIRST `user` message in a transcript."""
    with jsonl_path.open() as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "user":
                continue
            content = (rec.get("message") or {}).get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block.get("text") or ""
            return None
    return None


def _identify_agent(jsonl_path: Path) -> tuple[str, str] | None:
    """Return (agent_id, family) for this transcript, or None if unidentifiable."""
    head = _first_user_text(jsonl_path)
    if not head:
        return None
    m = _WORKDIR_RE.search(head)
    if not m:
        return None
    workdir = Path(m.group(1))
    # canonical_eval expects the path to the final-model folder; but its
    # derivation only looks for an `agent-NN` ancestor and the module name above.
    # Pass the agent dir directly — the derivation walks parts and tolerates
    # `agent-NN` as the trailing segment.
    if workdir.name == "":
        workdir = workdir.parent
    try:
        return derive_agent_id_and_family(workdir)
    except Exception:
        return None


def _sum_usage(jsonl_path: Path) -> dict:
    """Sum the usage fields across all assistant messages in this transcript."""
    totals = {k: 0 for k in USAGE_FIELDS}
    n_turns = 0
    with jsonl_path.open() as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "assistant":
                continue
            u = (rec.get("message") or {}).get("usage") or {}
            if not u:
                continue
            n_turns += 1
            for k in USAGE_FIELDS:
                v = u.get(k)
                if isinstance(v, (int, float)):
                    totals[k] += int(v)
    totals["total_tokens"] = sum(totals[k] for k in USAGE_FIELDS)
    totals["n_assistant_turns"] = n_turns
    return totals


def collect_usage(
    wanted_agent_ids: set[str] | None = None,
    cwd: Path | None = None,
) -> dict[str, dict]:
    """Scan ~/.claude/projects/<proj>/*/subagents/*.jsonl and build a per-agent
    usage map. If `wanted_agent_ids` is given, only those agents are kept (other
    transcripts are still scanned to identify, but discarded if not wanted).

    When an agent has multiple transcripts (re-launches), keeps the one with the
    most recent mtime.
    """
    root = project_transcripts_root(cwd)
    if not root.is_dir():
        return {}

    # Gather candidates: every agent-*.jsonl under any subagents/ dir.
    candidates = sorted(root.glob("*/subagents/agent-*.jsonl"))

    by_agent: dict[str, dict] = {}
    for jp in candidates:
        ident = _identify_agent(jp)
        if not ident:
            continue
        agent_id, family = ident
        if wanted_agent_ids is not None and agent_id not in wanted_agent_ids:
            continue
        mtime = jp.stat().st_mtime
        prev = by_agent.get(agent_id)
        if prev is not None and prev["_mtime"] >= mtime:
            continue
        usage = _sum_usage(jp)
        usage["family"] = family
        usage["transcript_path"] = str(jp)
        usage["transcript_mtime_iso"] = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
        usage["_mtime"] = mtime
        by_agent[agent_id] = usage

    # Strip the private sort key before returning.
    for rec in by_agent.values():
        rec.pop("_mtime", None)
    return by_agent


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--cwd", type=Path, default=None,
                   help="Project cwd (default: current). Used to locate ~/.claude/projects/<encoded>.")
    p.add_argument("--agent-id", action="append", default=None,
                   help="Restrict to these agent_ids (repeatable). Default: all.")
    p.add_argument("--out", type=Path, default=None, help="Write JSON here. Default: stdout.")
    args = p.parse_args()

    wanted = set(args.agent_id) if args.agent_id else None
    usage = collect_usage(wanted_agent_ids=wanted, cwd=args.cwd)
    blob = json.dumps(usage, indent=2)
    if args.out:
        args.out.write_text(blob)
        print(f"usage: wrote {len(usage)} agent records -> {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(blob + "\n")


if __name__ == "__main__":
    main()
