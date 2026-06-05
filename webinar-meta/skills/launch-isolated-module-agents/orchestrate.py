#!/usr/bin/env python3
"""One-call orchestrator — read <angle>/.launch-config.json, run pre-flight,
snapshot, render prompts. Prints a tagged invocations payload for the parent
assistant to fire as Agent() calls.

The parent assistant should:
    1. Call this script.
    2. If it exits 0, read the printed JSON between BEGIN_INVOCATIONS / END_INVOCATIONS.
    3. Fire one Agent() per entry, all in a single message, run_in_background=true.
    4. When all return, call:  orchestrate.py <angle-root> --verify

Usage:
    # explicit angle root (legacy / advanced)
    python3 orchestrate.py <angle-root>
    python3 orchestrate.py <angle-root> --verify

    # shortcut: provision N slots in module-M for idea-I, then launch
    python3 orchestrate.py --module 3 --idea 1 --count 5
    python3 orchestrate.py --module 3 --idea 1 --count 5 --verify
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
PRE_FLIGHT = SKILL_DIR / "pre-flight-check.py"
LAUNCH_ALL = SKILL_DIR / "launch-all.py"
POST_VERIFY = SKILL_DIR / "post-run-verify.py"
PROVISION = SKILL_DIR / "provision-slots.py"
REPO_ROOT = SKILL_DIR.parents[2]


def fail(msg: str, rc: int = 1) -> None:
    print(f"orchestrate: {msg}", file=sys.stderr)
    sys.exit(rc)


def load_config(angle_root: Path) -> dict:
    cfg_file = angle_root / ".launch-config.json"
    if not cfg_file.is_file():
        fail(f"missing {cfg_file}. Create one (see skill README for schema).")
    cfg = json.loads(cfg_file.read_text())
    for key in ("modules", "extra_forbidden"):
        if key not in cfg:
            fail(f"{cfg_file} missing required key: {key}")
    return cfg


def write_manifest(cfg: dict, dst: Path) -> Path:
    dst.write_text(json.dumps(cfg["modules"], indent=2))
    return dst


def latest_launch_dir(angle_root: Path) -> Path:
    launches = sorted((angle_root / "_launch").glob("[0-9]*"))
    if not launches:
        fail(f"no launches under {angle_root / '_launch'}")
    return launches[-1]


def mark_current_launch(repo_root: Path, launch_id: str) -> None:
    f = repo_root / ".claude" / "current-launch.txt"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(launch_id + "\n")


def cmd_launch(angle_root: Path) -> int:
    cfg = load_config(angle_root)
    repo_root = angle_root.parent
    manifest = write_manifest(cfg, angle_root / "_launch" / "manifest.json")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest = write_manifest(cfg, manifest)

    print("─── 1/3 pre-flight ───")
    rc = subprocess.call(["python3", str(PRE_FLIGHT), str(manifest)])
    if rc != 0:
        fail("pre-flight failed — fix the substrate, don't bypass.", 1)

    print("\n─── 2/3 launch-all (snapshot + prompts + invocations) ───")
    extra_args: list[str] = ["--angle-root", str(angle_root), "--repo-root", str(repo_root)]
    for f in cfg["extra_forbidden"]:
        extra_args += ["--extra-forbidden", f]
    rc = subprocess.call(["python3", str(LAUNCH_ALL), str(manifest)] + extra_args)
    if rc != 0:
        fail("launch-all failed", 1)

    launch_dir = latest_launch_dir(angle_root)
    launch_id = f"{angle_root.name}/{launch_dir.name}"
    mark_current_launch(repo_root, launch_id)

    invocations_file = launch_dir / "invocations.json"
    invocations = json.loads(invocations_file.read_text())
    # Strip the `prompt_file` field — the parent only needs `prompt`.
    payload = [
        {"subagent_type": inv["subagent_type"],
         "description": inv["description"],
         "run_in_background": inv["run_in_background"],
         "prompt": inv["prompt"]}
        for inv in invocations
    ]
    print(f"\n─── 3/3 invocations for parent assistant ───")
    print(f"launch_id: {launch_id}")
    print(f"launch_dir: {launch_dir}")
    print("BEGIN_INVOCATIONS")
    print(json.dumps(payload))
    print("END_INVOCATIONS")
    print()
    print(f"Next:  fire all {len(payload)} Agent() calls in ONE message (run_in_background=true).")
    print(f"After: python3 {Path(__file__).name} {angle_root} --verify")
    return 0


def cmd_verify(angle_root: Path) -> int:
    cfg = load_config(angle_root)
    manifest = angle_root / "_launch" / "manifest.json"
    if not manifest.is_file():
        # Re-emit from config.
        write_manifest(cfg, manifest)
    launch_dir = latest_launch_dir(angle_root)
    print(f"verifying launch_dir={launch_dir}")
    rc = subprocess.call([
        "python3", str(POST_VERIFY), str(manifest),
        "--launch-dir", str(launch_dir),
    ])
    # Surface the hook log too.
    hook_log = angle_root.parent / ".claude" / "blocked-attempts.log"
    if hook_log.is_file():
        size = hook_log.stat().st_size
        print(f"\nhook log: {hook_log} ({size} bytes)")
        if size > 0:
            print("  recent entries (last 5):")
            lines = hook_log.read_text().splitlines()[-5:]
            for line in lines:
                print(f"    {line}")
    else:
        print("\nhook log: none (hook may not be active for this session — check repo-root .claude/settings.json)")
    return rc


def cmd_provision(module: int, idea: int, count: int) -> Path:
    """Run provision-slots.py and return the angle-root it produced."""
    rc = subprocess.call([
        "python3", str(PROVISION),
        "--module", str(module),
        "--idea", str(idea),
        "--count", str(count),
        "--repo-root", str(REPO_ROOT),
    ])
    if rc != 0:
        fail("provisioning failed", 1)
    return REPO_ROOT / "cohort-runs"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("angle_root", type=Path, nargs="?",
                   help="path containing .launch-config.json (omit when using --module/--idea/--count)")
    p.add_argument("--verify", action="store_true",
                   help="Run post-run-verify on the most recent launch under <angle-root>/_launch/")
    p.add_argument("--module", type=int,
                   help="module number 1..4 (shortcut: provisions slots first)")
    p.add_argument("--idea", type=int,
                   help="idea number, e.g. 1 (shortcut)")
    p.add_argument("--count", type=int,
                   help="number of agents to launch (shortcut)")
    args = p.parse_args()

    shortcut = args.module is not None or args.idea is not None or args.count is not None
    if shortcut:
        if not (args.module and args.idea and args.count):
            fail("shortcut needs all three: --module M --idea I --count N", 2)
        if args.angle_root is not None:
            fail("pass either angle_root OR --module/--idea/--count, not both", 2)
        angle_root = cmd_provision(args.module, args.idea, args.count)
    else:
        if args.angle_root is None:
            fail("missing angle_root (or use --module/--idea/--count)", 2)
        angle_root = args.angle_root.resolve(strict=False)

    if not angle_root.is_dir():
        fail(f"angle root not a directory: {angle_root}", 2)

    if args.verify:
        sys.exit(cmd_verify(angle_root))
    else:
        sys.exit(cmd_launch(angle_root))


if __name__ == "__main__":
    main()
