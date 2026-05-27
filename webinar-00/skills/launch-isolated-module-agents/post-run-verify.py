#!/usr/bin/env python3
"""Post-run verification — three-way cross-check that isolation held during a
multi-agent run.

Usage:
    python3 post-run-verify.py <manifest.json> --launch-dir <angle>/_launch/<timestamp>

Three views, per module:
    [V1] Self-report — parse the agent's ISOLATION_REPORT: block from REPORT.md.
         Flag any path the agent admits reading outside its allow-list.
    [V2] Filesystem diff — diff the current state of code/ and data/ against the
         pre-launch snapshot (snapshot.txt with md5 per file). Any new or
         modified file in shared dirs is a write-violation.
    [V3] Hook log — count blocked attempts in <launch-dir>/../blocked-attempts.log.
         Note: per-agent attribution is best-effort (the hook tags by session_id
         which is the parent session, not the subagent). Reports totals + any
         blocks that happened *during* the launch window.

Exit codes:
    0  if every module passes every view.
    1  if any module fails any view (workshop-relevant data, not a crash).
    2  if the inputs themselves are missing/malformed.
"""

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path


def md5_of(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_isolation_report(report_md: Path) -> dict | None:
    """Find the ISOLATION_REPORT: block in REPORT.md and parse the four lists."""
    if not report_md.is_file():
        return None
    text = report_md.read_text(errors="replace")
    m = re.search(r"ISOLATION_REPORT:\s*\n(.*?)(?:```|\Z)", text, re.DOTALL)
    if not m:
        return None
    body = m.group(1)
    out = {"read_outside_module": [], "attempted_blocked": [], "shared_dir_writes": [], "notes": ""}
    for key in out:
        if key == "notes":
            mm = re.search(rf'{key}:\s*"([^"]*)"', body)
            if mm:
                out[key] = mm.group(1)
        else:
            mm = re.search(rf"{key}:\s*\[(.*?)\]", body, re.DOTALL)
            if mm:
                inner = mm.group(1).strip()
                if inner:
                    # split by comma, strip quotes and whitespace
                    items = [s.strip().strip('"').strip("'") for s in inner.split(",")]
                    out[key] = [s for s in items if s]
    return out


def view_self_report(m: dict) -> tuple[bool, str]:
    report = Path(m["module_path"]) / "REPORT.md"
    parsed = parse_isolation_report(report)
    if parsed is None:
        return False, f"no parsable ISOLATION_REPORT in {report} (the agent forgot the mandatory tail, OR REPORT.md was never persisted)"
    issues = []
    if parsed["read_outside_module"]:
        issues.append(f"agent admits reads outside module: {parsed['read_outside_module']}")
    if parsed["shared_dir_writes"]:
        issues.append(f"agent admits writes to shared dirs: {parsed['shared_dir_writes']}")
    if issues:
        return False, "; ".join(issues) + (f" — notes: {parsed['notes']}" if parsed['notes'] else "")
    extra = f" (attempted_blocked={parsed['attempted_blocked']})" if parsed['attempted_blocked'] else ""
    return True, f"clean self-report{extra}"


def view_filesystem_diff(launch_dir: Path) -> tuple[bool, str]:
    """Compare the live state of code/ and data/ against the snapshot."""
    snap = launch_dir / "snapshot.txt"
    if not snap.is_file():
        return False, f"no snapshot at {snap} — was launch-all.py run?"
    snap_map: dict[str, str] = {}
    for line in snap.read_text().splitlines():
        if not line.strip():
            continue
        try:
            h, p = line.split("\t", 1)
            snap_map[p] = h
        except ValueError:
            continue

    # Re-compute current state for the same paths.
    changed: list[str] = []
    missing: list[str] = []
    added: list[str] = []
    snap_paths = set(snap_map.keys())

    # We snapshot relative to the angle root. Recompute by walking the same roots.
    # Roots are inferred from snapshot path prefixes: take unique top-level dirs.
    roots: set[Path] = set()
    for p in snap_paths:
        try:
            roots.add(Path(p).parents[len(Path(p).parents) - 2])  # /a/b/c -> /a
        except IndexError:
            continue
    # Above is fragile; rely instead on the convention that snapshots only
    # contain absolute paths under {code,data}. Re-walk those.
    for p in list(snap_paths):
        ap = Path(p)
        if not ap.exists():
            missing.append(p)
            continue
        try:
            cur = md5_of(ap)
        except (PermissionError, OSError):
            continue
        if cur != snap_map[p]:
            changed.append(p)

    # Find added files under the union of snapshot parent roots.
    parent_roots: set[Path] = set()
    for p in snap_paths:
        parts = Path(p).parts
        # Find first occurrence of 'code' or 'data' in parts and take prefix up to it.
        for i, part in enumerate(parts):
            if part in ("code", "data"):
                parent_roots.add(Path(*parts[: i + 1]))
                break
    for root in parent_roots:
        if not root.is_dir():
            continue
        for sub in root.rglob("*"):
            if sub.is_file():
                key = str(sub)
                if key not in snap_paths:
                    added.append(key)

    issues = []
    if changed:
        issues.append(f"{len(changed)} files modified under shared dirs (first 5): {changed[:5]}")
    if added:
        issues.append(f"{len(added)} files added under shared dirs (first 5): {added[:5]}")
    if missing:
        issues.append(f"{len(missing)} files vanished under shared dirs (first 5): {missing[:5]}")
    if issues:
        return False, "; ".join(issues)
    return True, f"shared dirs unchanged ({len(snap_paths)} files snapshotted)"


def view_hook_log(launch_dir: Path, window_start: datetime.datetime) -> tuple[bool, str]:
    log = launch_dir / "blocked-attempts.log"
    if not log.is_file():
        return True, "no hook log present (hook may not be wired; this view skipped)"
    n_total = 0
    n_in_window = 0
    samples: list[str] = []
    for line in log.read_text().splitlines():
        if not line.strip():
            continue
        n_total += 1
        try:
            ts_str = line.split("\t", 1)[0]
            ts = datetime.datetime.fromisoformat(ts_str)
            if ts >= window_start:
                n_in_window += 1
                if len(samples) < 5:
                    samples.append(line)
        except Exception:
            continue
    # Hook BLOCKS were the hook doing its job. The signal here is "are there
    # blocked attempts at all" — non-zero means the prompt-soft layer failed
    # at least once but the hard layer caught it. That's a workshop talking
    # point either way; we report but don't fail on it.
    msg = f"{n_in_window} blocked attempts during launch window ({n_total} all-time)"
    if samples:
        msg += f"; samples: {samples}"
    return True, msg


def main():
    p = argparse.ArgumentParser()
    p.add_argument("manifest", type=Path)
    p.add_argument("--launch-dir", required=True, type=Path)
    args = p.parse_args()

    if not args.manifest.is_file():
        print(f"ERROR: manifest not found: {args.manifest}", file=sys.stderr)
        sys.exit(2)
    if not args.launch_dir.is_dir():
        print(f"ERROR: launch-dir not found: {args.launch_dir}", file=sys.stderr)
        sys.exit(2)

    manifest = json.loads(args.manifest.read_text())
    # Window start = mtime of the snapshot file.
    snap = args.launch_dir / "snapshot.txt"
    window_start = datetime.datetime.fromtimestamp(snap.stat().st_mtime) if snap.is_file() else datetime.datetime.min

    all_ok = True
    print(f"post-run-verify: {len(manifest)} modules; launch-dir={args.launch_dir}; window_start={window_start.isoformat()}")
    for m in manifest:
        print(f"\nmodule: {m.get('module_name')}")
        ok1, msg1 = view_self_report(m)
        print(f"  [V1 self-report]  {'OK' if ok1 else 'FAIL'} — {msg1}")
        ok2, msg2 = view_filesystem_diff(args.launch_dir)
        print(f"  [V2 fs-diff]      {'OK' if ok2 else 'FAIL'} — {msg2}")
        ok3, msg3 = view_hook_log(args.launch_dir, window_start)
        print(f"  [V3 hook log]     {'OK' if ok3 else 'FAIL'} — {msg3}")
        if not (ok1 and ok2 and ok3):
            all_ok = False

    print()
    if all_ok:
        print("post-run-verify: ALL CLEAN")
        sys.exit(0)
    else:
        print("post-run-verify: violations or gaps detected — capture in your run-log.")
        sys.exit(1)


if __name__ == "__main__":
    main()
