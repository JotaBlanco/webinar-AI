#!/usr/bin/env python3
"""PreToolUse hook — static-policy content firewall for the webinar-AI repo.

Wired in <repo-root>/.claude/settings.json (single, repo-wide). The hook is
intentionally policy-only (no per-angle config) — it enforces a static map of
what reads are always-safe, always-denied, or never-relevant:

ALLOWED reads (no logging, exit 0):
  - <repo-root>/webinar-angle-*/modulo-*/**     (any module in any angle — intra-angle
                                                 isolation is the prompt's job, not ours)
  - <repo-root>/code/**                         (shared runtime code)
  - <repo-root>/data/**                         (shared runtime data)
  - <repo-root>/webinar-meta/skills/launch-isolated-module-agents/**
                                                (this skill — orchestrator etc.)
  - any path outside <repo-root>                (we're not a general-purpose firewall;
                                                 system tools, system python, /tmp, etc.
                                                 are fine)

DENIED reads (exit 2, log line written):
  - <repo-root>/webinar-angle-*/_shared/**
  - <repo-root>/webinar-angle-*/_launch/**
  - <repo-root>/webinar-angle-*/_observations/**
  - <repo-root>/webinar-angle-*/process-log.md
  - <repo-root>/webinar-angle-*/RUN-LOG.md
  - <repo-root>/webinar-AI/webinar-meta/webinar-00-template-*/**
  - <repo-root>/webinar-AI/webinar-meta/domain-knowledge-challenges/**
  - any path matching <repo-root>/<extra-denies-glob>/** (from --extra-deny arg)

Bypass (for the human-driven main session only — never set these in env/files
shared with subagents):
  - env var WEBINAR_AI_ADMIN=1   — durable, requires Claude Code restart after set
  - file <repo-root>/.claude/main-session-unlock — live toggle (touch/rm)
  Either one causes the hook to exit 0 immediately and log a BYPASS line.

What this DOESN'T enforce:
  - Cross-angle reads (M1 of angle-C reading something from angle-A's modulo-2).
    Each angle's prompt template says "only read from your own module" but we
    don't have per-agent state to enforce it. If the cross-angle module path
    has nothing identifying which one the agent "should" be in, we cannot
    distinguish "right module of another angle" from "right module of own angle".
  - Sister KBs by default. Pass --extra-deny <abs-path> to add them (e.g.
    /Users/javiquix/Desktop/quixdev/F1).

Logging:
  Every denied attempt is appended to <repo-root>/.claude/blocked-attempts.log
  with timestamp, session_id, tool name, and resolved path. The launch-id (which
  Run #N is active) is taken from <repo-root>/.claude/current-launch.txt if
  present, else "unscoped".

Hook protocol:
  - Input via stdin JSON: {session_id, transcript_path, cwd, tool_name, tool_input, ...}
  - Exit 0 → allow
  - Exit 2 → block (Claude Code displays stderr to user/agent)
  - Any other non-zero → non-blocking error

Usage:
    python3 hook-blocker.py --repo-root /abs/path/to/webinar-AI [--extra-deny /abs/path ...]
"""

import argparse
import datetime
import fnmatch
import json
import os
import re
import shlex
import sys
from pathlib import Path

PATH_TAKING_CMDS = {
    "cat", "head", "tail", "less", "more", "bat",
    "grep", "egrep", "fgrep", "rg",
    "awk", "sed",
    "find",
    "ls", "stat", "file", "wc",
    "cp", "mv", "rm", "ln",
    "diff", "cmp",
    "python", "python3", "node", "deno",
    "tar", "zip", "unzip", "gzip", "gunzip",
    "open", "code", "vim", "nano",
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", required=True, type=Path)
    p.add_argument("--extra-deny", action="append", default=[], type=Path,
                   help="Additional absolute path prefix to deny (repeat).")
    p.add_argument("--allow-module", action="append", default=[], type=str,
                   help="Module folder name (e.g. module-4) to whitelist back in "
                        "from the DENY_PATTERNS_REL list. Repeat for multiple. "
                        "Use for the cohort that is currently active.")
    return p.parse_args()


def extract_paths_from_bash(cmd_str: str) -> list[str]:
    paths = []
    chunks = re.split(r"\s*(?:&&|\|\||;|\|)\s*", cmd_str)
    seen = set()
    for chunk in chunks:
        try:
            tokens = shlex.split(chunk)
        except ValueError:
            tokens = chunk.split()
        if not tokens:
            continue
        cmd = os.path.basename(tokens[0])
        if cmd in PATH_TAKING_CMDS:
            for t in tokens[1:]:
                if t.startswith("-"):
                    continue
                if t.startswith(("/", "~", "./", "../")) or "/" in t:
                    if t not in seen:
                        paths.append(t)
                        seen.add(t)
        for t in tokens:
            if t.startswith("/"):
                clean = t.split("=", 1)[-1] if "=" in t else t
                if clean.startswith("/") and clean not in seen:
                    paths.append(clean)
                    seen.add(clean)
    return paths


def canonical(p: str, cwd: Path) -> Path | None:
    try:
        path = Path(p).expanduser()
        if not path.is_absolute():
            path = cwd / path
        return path.resolve(strict=False)
    except Exception:
        return None


# DENIED policy — patterns relative to repo_root. Use fnmatch globs.
#
# Layer 3 is the ONLY hard-isolation layer that propagates to Task subagents
# (verified by smoke test 2026-05-31; declarative `settings.json permissions.deny`
# is parent-only). So this list must mirror the intent of settings.json deny.
DENY_PATTERNS_REL = [
    # ── Prior angle cohorts (cross-angle isolation) ──────────────────────
    "webinar-angle-*/_shared/*",
    "webinar-angle-*/_shared/**",
    "webinar-angle-*/_launch/*",
    "webinar-angle-*/_launch/**",
    "webinar-angle-*/_observations/*",
    "webinar-angle-*/_observations/**",
    "webinar-angle-*/process-log.md",
    "webinar-angle-*/RUN-LOG.md",
    "webinar-angle-*/.launch-config.json",

    # ── Substrate that agents must not see (templates, design KB, grading skill) ──
    # The grading skill source is the most sensitive: if an agent reads the
    # canonical YAML or worker.py they know exactly what is being measured and
    # could game it without learning anything.
    "webinar-meta/**",
    "webinar-meta/*",

    # ── Prior-cohort module folders (cross-module isolation) ──────────────
    # Cohort N agents must not read cohort M's work. Pass --allow-module
    # module-X to whitelist a specific module folder back in (for the active
    # cohort). Intra-cohort (agent-01 reading agent-02 within same module)
    # CANNOT be enforced here — the hook is per-project, not per-subagent.
    "module-1/**",
    "module-1/*",
    "module-2/**",
    "module-2/*",
    "module-3/**",
    "module-3/*",
    "module-4/**",
    "module-4/*",

    # ── Historical / experimental dirs agents shouldn't read ──────────────
    "deprecated/**",
    "deprecated/*",
    "raw-model/**",
    "raw-model/*",
    "_grade/**",
    "_grade/*",
]


def is_denied(path: Path, repo_root: Path, extra_deny: list[Path],
              allow_modules: list[str]) -> bool:
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        # Outside repo_root — check extra_deny only.
        for ed in extra_deny:
            ed_c = ed.resolve(strict=False)
            if str(path) == str(ed_c) or str(path).startswith(str(ed_c) + os.sep):
                return True
        return False
    rel_str = str(rel)
    # Per-cohort allowlist override: if the active cohort is module-N, the
    # `--allow-module module-N` arg whitelists `module-N/**` back in even though
    # `module-N/**` is in DENY_PATTERNS_REL. Lets one config support many cohorts.
    for am in allow_modules:
        am = am.strip("/")
        if rel_str == am or rel_str.startswith(am + "/"):
            return False
    for pat in DENY_PATTERNS_REL:
        if fnmatch.fnmatch(rel_str, pat):
            return True
    return False


def current_launch_id(repo_root: Path) -> str:
    f = repo_root / ".claude" / "current-launch.txt"
    if f.is_file():
        return f.read_text().strip() or "unscoped"
    return "unscoped"


def bypass_active(repo_root: Path) -> str | None:
    """Return a short reason if the human-driven main-session bypass is on, else None."""
    if os.environ.get("WEBINAR_AI_ADMIN") == "1":
        return "env:WEBINAR_AI_ADMIN=1"
    unlock = repo_root / ".claude" / "main-session-unlock"
    if unlock.is_file():
        return f"file:{unlock}"
    return None


def main():
    args = parse_args()
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        print(f"hook-blocker: cannot parse stdin: {e}", file=sys.stderr)
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    cwd = Path(payload.get("cwd", os.getcwd()))
    session_id = payload.get("session_id", "unknown")

    repo_root = args.repo_root.resolve(strict=False)
    extra_deny = [Path(p).resolve(strict=False) for p in args.extra_deny]

    bypass = bypass_active(repo_root)
    if bypass:
        # Log the bypass (so it's visible after the fact), then allow.
        try:
            log_dir = repo_root / ".claude"
            log_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.now().isoformat(timespec="seconds")
            with open(log_dir / "blocked-attempts.log", "a") as f:
                f.write(f"{ts}\t{current_launch_id(repo_root)}\t{session_id}\t{tool_name}\tBYPASS\t({bypass})\n")
        except Exception:
            pass
        sys.exit(0)

    candidates: list[str] = []
    if tool_name in ("Read", "Edit", "Write"):
        fp = tool_input.get("file_path")
        if fp:
            candidates.append(fp)
    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")
        candidates.extend(extract_paths_from_bash(cmd))

    if not candidates:
        sys.exit(0)

    blocked: list[tuple[str, Path]] = []
    seen_canon: set[Path] = set()
    for c in candidates:
        canon = canonical(c, cwd)
        if canon is None or canon in seen_canon:
            continue
        seen_canon.add(canon)
        if is_denied(canon, repo_root, extra_deny, args.allow_module):
            blocked.append((c, canon))

    if not blocked:
        sys.exit(0)

    # Log + block.
    launch_id = current_launch_id(repo_root)
    log_dir = repo_root / ".claude"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "blocked-attempts.log"
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    with open(log_file, "a") as f:
        for raw, canon in blocked:
            f.write(f"{ts}\t{launch_id}\t{session_id}\t{tool_name}\t{canon}\t(raw={raw})\n")

    print(
        f"hook-blocker: out-of-scope path(s) — denied by policy.\n"
        f"  tool: {tool_name}\n"
        f"  blocked: {[str(p) for _, p in blocked]}\n"
        f"  policy: webinar-angle-*/_shared|_launch|_observations|process-log.md|RUN-LOG.md, "
        f"webinar-meta/**, module-1/2/3/4/**, deprecated/**, raw-model/**, _grade/**, plus --extra-deny. "
        f"--allow-module={args.allow_module or 'none'} whitelists the active cohort.\n"
        f"  logged to: {log_file}\n"
        f"If this read is genuinely needed, declare a limitation in REPORT.md and proceed without.",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
