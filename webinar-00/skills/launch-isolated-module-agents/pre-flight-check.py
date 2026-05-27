#!/usr/bin/env python3
"""Pre-flight check — refuse to clear an isolated-agents launch until the substrate
is sane. Catches the recurring bugs we've hit across angles A, B, C.

Usage:
    python3 pre-flight-check.py <manifest.json>

Manifest shape:
    [
      {
        "module_name": "modulo-1",
        "module_path": "/abs/path/to/webinar-angle-C/modulo-1",
        "harness_components_present": ["tools (1)", "context-seed (3)"],
        "task_relative_path": "tasks/challenge.md",
        "time_budget_minutes": 25
      },
      ...
    ]

Exits 0 iff every module passes every check. Otherwise non-zero with a
per-module failure breakdown.

Checks per module:
    [P1] module_path exists and is a directory
    [P2] task_relative_path resolves to a file under module_path
    [P3] code/ and data/ inside module are symlinks that resolve to existing dirs
    [P4] python3 -c "import pandas, numpy" works from the module dir
    [P5] If AGENTS.md mentions `.venv`, that venv actually exists (the A1 trap)
    [P6] Test-write a probe file named REPORT.md in the module; succeeds means
         the parent harness doesn't block .md writes. (Note: this is the parent
         harness; subagents have their own block. We test parent so a true
         override can be detected too.)
    [P7] Nothing in the manifest references a module_path that contains another
         module's name (sanity — paths don't overlap).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


CHECKS = ["P1", "P2", "P3", "P4", "P5", "P6", "P7"]


def check_module(m: dict) -> dict:
    """Return {check_id: (ok, message)} for one module."""
    out: dict[str, tuple[bool, str]] = {}
    mod_path = Path(m["module_path"])

    # P1 — exists
    out["P1"] = (mod_path.is_dir(), f"module_path={mod_path}")

    # P2 — task file
    task = mod_path / m["task_relative_path"]
    out["P2"] = (task.is_file(), f"task={task}")

    # P3 — symlinks
    code_link = mod_path / "code"
    data_link = mod_path / "data"
    code_ok = code_link.is_symlink() and code_link.resolve(strict=False).is_dir()
    data_ok = data_link.is_symlink() and data_link.resolve(strict=False).is_dir()
    out["P3"] = (code_ok and data_ok, f"code_symlink={code_link.is_symlink()}({code_link.resolve(strict=False)}), data_symlink={data_link.is_symlink()}({data_link.resolve(strict=False)})")

    # P4 — deps
    py_check = subprocess.run(
        ["python3", "-c", "import pandas, numpy, scipy, matplotlib"],
        cwd=mod_path if mod_path.is_dir() else None,
        capture_output=True,
        text=True,
    )
    out["P4"] = (py_check.returncode == 0, f"python3 imports rc={py_check.returncode}: {py_check.stderr.strip()[:200]}")

    # P5 — .venv referenced in AGENTS.md but missing
    agents_md = mod_path / "AGENTS.md"
    if agents_md.is_file():
        content = agents_md.read_text(errors="replace")
        if ".venv" in content:
            # Look for .venv at common locations
            possible = [mod_path / ".venv", mod_path.parent / ".venv", mod_path.parent.parent / ".venv"]
            venv_exists = any(p.is_dir() for p in possible)
            out["P5"] = (venv_exists, f"AGENTS.md mentions .venv; venv_exists in {[str(p) for p in possible]}: {venv_exists}")
        else:
            out["P5"] = (True, "no .venv mention in AGENTS.md (skipped)")
    else:
        out["P5"] = (True, "no AGENTS.md (skipped — module 1 of angle-C, or similar)")

    # P6 — probe write a REPORT.md
    probe = mod_path / "_preflight_probe_REPORT.md"
    try:
        probe.write_text("preflight probe — safe to delete\n")
        probe.unlink()
        out["P6"] = (True, "REPORT.md probe write+delete OK (parent harness allows .md writes)")
    except Exception as e:
        out["P6"] = (False, f"REPORT.md probe failed: {e}")

    return out


def check_manifest_global(manifest: list[dict]) -> tuple[bool, str]:
    """P7 — module_paths are unique full paths, and no path contains another."""
    paths = [Path(m["module_path"]).resolve(strict=False) for m in manifest]
    if len(set(paths)) != len(paths):
        return False, "duplicate module_path entries"
    mod_names = [m["module_name"] for m in manifest]
    if len(set(mod_names)) != len(mod_names):
        return False, f"duplicate module_name entries: {mod_names}"
    for a in paths:
        for b in paths:
            if a == b:
                continue
            if str(a).startswith(str(b) + os.sep):
                return False, f"{a} is inside {b}"
    return True, "no overlap"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("manifest", type=Path)
    args = p.parse_args()

    manifest = json.loads(args.manifest.read_text())
    if not isinstance(manifest, list) or not manifest:
        print("ERROR: manifest must be a non-empty JSON array.", file=sys.stderr)
        sys.exit(2)

    print(f"pre-flight: {len(manifest)} modules")
    all_ok = True

    # P7 — global
    p7_ok, p7_msg = check_manifest_global(manifest)
    print(f"  [P7] global path-overlap check: {'OK' if p7_ok else 'FAIL'} — {p7_msg}")
    if not p7_ok:
        all_ok = False

    # Per-module
    for m in manifest:
        print(f"\nmodule: {m.get('module_name')}")
        results = check_module(m)
        for cid in CHECKS:
            if cid == "P7":
                continue
            ok, msg = results[cid]
            print(f"  [{cid}] {'OK' if ok else 'FAIL'} — {msg}")
            if not ok:
                all_ok = False

    print()
    if all_ok:
        print("pre-flight: ALL OK — safe to launch")
        sys.exit(0)
    else:
        print("pre-flight: FAILURES present — fix the substrate, don't bypass.")
        sys.exit(1)


if __name__ == "__main__":
    main()
