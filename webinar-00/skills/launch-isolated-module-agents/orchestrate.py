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
    python3 orchestrate.py <angle-root>             # pre-flight + launch
    python3 orchestrate.py <angle-root> --verify    # post-run-verify the most-recent launch
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("angle_root", type=Path)
    p.add_argument("--verify", action="store_true",
                   help="Run post-run-verify on the most recent launch under <angle-root>/_launch/")
    args = p.parse_args()

    angle_root = args.angle_root.resolve(strict=False)
    if not angle_root.is_dir():
        fail(f"angle root not a directory: {angle_root}", 2)

    if args.verify:
        sys.exit(cmd_verify(angle_root))
    else:
        sys.exit(cmd_launch(angle_root))


if __name__ == "__main__":
    main()
