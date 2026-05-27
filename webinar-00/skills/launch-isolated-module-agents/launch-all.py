#!/usr/bin/env python3
"""Orchestrator — materialise prompts, snapshot shared dirs, and emit the Agent
tool invocations that the parent assistant must paste into a single message.

Usage:
    python3 launch-all.py <manifest.json> [--repo-root /abs/path/to/webinar-AI] \\
                                           [--angle-root /abs/path/to/webinar-angle-C]

What it produces (under <angle-root>/_launch/<timestamp>/):
    snapshot.txt             # md5 per file under code/ and data/ (the read-only contract baseline)
    <module>.prompt.md       # one filled prompt per module
    invocations.json         # the Agent tool calls to fire; copy/paste into the assistant

Does NOT call the Agent tool itself — only the parent assistant can do that.
The orchestrator's role is to prepare a deterministic, auditable launch packet.
"""

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path


def md5_of(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(roots: list[Path], out: Path) -> int:
    """Walk roots, write `<md5>\\t<abs-path>` per file. Returns file count."""
    n = 0
    with open(out, "w") as f:
        for root in roots:
            if not root.is_dir():
                continue
            for sub in sorted(root.rglob("*")):
                if not sub.is_file():
                    continue
                try:
                    h = md5_of(sub)
                except (PermissionError, OSError):
                    continue
                f.write(f"{h}\t{sub}\n")
                n += 1
    return n


def fill_template(template: str, module: dict, angle_name: str,
                  shared_code: Path, shared_data: Path,
                  forbidden_reads: list[str]) -> str:
    out = template
    components_md = "\n".join(f"- **{c}**" for c in module["harness_components_present"])
    forbidden_md = "\n".join(f"- `{p}`" for p in forbidden_reads)
    repl = {
        "{{module_name}}": module["module_name"],
        "{{module_path}}": module["module_path"],
        "{{angle_name}}": angle_name,
        "{{shared_code_path}}": str(shared_code),
        "{{shared_data_path}}": str(shared_data),
        "{{task_relative_path}}": module["task_relative_path"],
        "{{time_budget_minutes}}": str(module.get("time_budget_minutes", 25)),
        "{{harness_components_list}}": components_md,
        "{{forbidden_reads_list}}": forbidden_md,
    }
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("manifest", type=Path)
    p.add_argument("--repo-root", type=Path, default=None,
                   help="webinar-AI repo root (inferred from manifest module paths if omitted)")
    p.add_argument("--angle-root", type=Path, default=None,
                   help="current angle root (inferred from manifest module paths if omitted)")
    p.add_argument("--extra-forbidden", type=Path, action="append", default=[],
                   help="Additional absolute path to forbid (repeat for multiple). "
                        "Use for sister KBs, project archives, anything outside the angle "
                        "but plausibly readable. Only paths that exist on disk are included.")
    args = p.parse_args()

    manifest = json.loads(args.manifest.read_text())
    if not manifest:
        print("ERROR: empty manifest", file=sys.stderr)
        sys.exit(2)

    # Infer roots if not given.
    module_paths = [Path(m["module_path"]) for m in manifest]
    if args.angle_root is None:
        args.angle_root = module_paths[0].parent
    if args.repo_root is None:
        args.repo_root = args.angle_root.parent

    shared_code = (args.repo_root / "code").resolve(strict=False)
    shared_data = (args.repo_root / "data").resolve(strict=False)
    angle_name = args.angle_root.name

    # Output dir
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.angle_root / "_launch" / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Snapshot shared dirs
    snap_file = out_dir / "snapshot.txt"
    n_snap = snapshot([shared_code, shared_data], snap_file)
    print(f"snapshot: {n_snap} files -> {snap_file}")

    # 2) Build forbidden-reads list per agent.
    # Pattern: forbid anything inside the repo that isn't the current angle,
    # plus _shared/_launch/_observations/log files within the current angle.
    # Plus any --extra-forbidden paths the user passes (sister KBs, archives, etc.).
    # CRITICAL: only include paths that actually exist on disk; emitting a path
    # that doesn't exist makes the rule look fake to the agent and weakens
    # respect for the rest of the list.
    repo = args.repo_root.resolve(strict=False)
    angle_name_actual = args.angle_root.name

    candidates = [
        # Other angles (skip self).
        repo / "webinar-00",
        repo / "webinar-angle-A",
        repo / "webinar-angle-B",
        repo / "webinar-angle-C",
        repo / "webinar-angle-D",
        # Current angle's shared/log files.
        args.angle_root / "_shared",
        args.angle_root / "_launch",
        args.angle_root / "_observations",
        args.angle_root / "process-log.md",
        args.angle_root / "RUN-LOG.md",
    ] + [Path(p) for p in args.extra_forbidden]

    common_forbidden = []
    for c in candidates:
        c_resolved = c.resolve(strict=False)
        # Skip the current angle itself.
        if c_resolved == args.angle_root.resolve(strict=False):
            continue
        # Only emit if it exists.
        if c_resolved.exists():
            common_forbidden.append(str(c_resolved))
        else:
            # Stash a note for visibility but don't include in agent's prompt.
            pass

    if not args.extra_forbidden:
        print("NOTE: no --extra-forbidden paths given. Sister KBs (if any) outside "
              "the repo are not in the forbidden list. Pass them explicitly with "
              "--extra-forbidden /abs/path/to/KB if you want the agent warned.")

    # Load template
    skill_dir = Path(__file__).resolve().parent
    template = (skill_dir / "prompt-template.md").read_text()
    # Strip the front-matter delimiter blob — keep only from first '---' onward
    parts = template.split("---", 2)
    if len(parts) >= 3:
        body = parts[2]
    else:
        body = template

    # 3) Per-module prompt + invocation
    invocations: list[dict] = []
    for m in manifest:
        per_mod_forbidden = list(common_forbidden) + [
            str(Path(p)) for p in module_paths
            if Path(p).name != m["module_name"]
        ]
        prompt_text = fill_template(body, m, angle_name, shared_code, shared_data, per_mod_forbidden)
        prompt_file = out_dir / f"{m['module_name']}.prompt.md"
        prompt_file.write_text(prompt_text)
        invocations.append({
            "subagent_type": "general-purpose",
            "description": f"{m['module_name']} isolated agent",
            "run_in_background": True,
            "prompt_file": str(prompt_file),
            "prompt": prompt_text,
        })

    inv_file = out_dir / "invocations.json"
    inv_file.write_text(json.dumps(invocations, indent=2))
    print(f"prompts: {len(invocations)} -> {out_dir}")
    print(f"invocations: {inv_file}")
    print()
    print("Next steps (parent assistant):")
    print("  1. Inspect each <module>.prompt.md; sanity-check the forbidden list.")
    print("  2. Paste one Agent() call per module from invocations.json INTO A SINGLE MESSAGE")
    print("     so they run in parallel.")
    print(f"  3. After all return, run post-run-verify.py {args.manifest} --launch-dir {out_dir}")


if __name__ == "__main__":
    main()
