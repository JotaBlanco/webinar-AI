#!/usr/bin/env python3
"""Provision agent slots for a (module, idea, count) launch.

Scans `<repo-root>/module-{M}/agent-*`, classifies each as FRESH or USED,
picks FRESH slots first, then mints new `agent-{NN}` folders by copying
`<repo-root>/webinar-meta/env-template-m{M}/` plus the idea's TASK.md.

Output: writes `<repo-root>/cohort-runs/.launch-config.json` with the N
selected slots (drawing per-slot template fields from
`webinar-meta/launch-configs/m{M}-idea-{II}.json`).

Used by `orchestrate.py --module M --idea I --count N`. Also runnable
standalone.

Classification — a slot is FRESH iff:
  - REPORT.md absent, AND
  - final-model/ absent OR contains nothing except .gitkeep

A stale TASK.md does NOT block reuse; this script overwrites TASK.md on
every provision so the slot lines up with the requested idea.
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

AGENT_DIR_RE = re.compile(r"^agent-(\d+)$")


def fail(msg: str, rc: int = 1) -> None:
    print(f"provision-slots: {msg}", file=sys.stderr)
    sys.exit(rc)


def is_fresh(agent_dir: Path) -> bool:
    if (agent_dir / "REPORT.md").is_file():
        return False
    fm = agent_dir / "final-model"
    if fm.is_dir():
        for p in fm.iterdir():
            if p.name != ".gitkeep":
                return False
    return True


def existing_slots(module_dir: Path) -> list[tuple[int, Path]]:
    slots = []
    if not module_dir.is_dir():
        return slots
    for p in sorted(module_dir.iterdir()):
        m = AGENT_DIR_RE.match(p.name)
        if m and p.is_dir():
            slots.append((int(m.group(1)), p))
    return slots


def next_agent_name(existing_indices: list[int]) -> str:
    n = (max(existing_indices) + 1) if existing_indices else 1
    return f"agent-{n:02d}"


def find_task_source(challenges_dir: Path, idea: int) -> Path:
    matches = sorted(challenges_dir.glob(f"idea-{idea:02d}-*.task.md"))
    if not matches:
        fail(
            f"no task source for idea-{idea:02d} under {challenges_dir}. "
            f"Expected file like idea-{idea:02d}-*.task.md."
        )
    return matches[0]


def mint_slot(agent_dir: Path, template_dir: Path, task_md: Path) -> None:
    """Create a fresh agent slot from env-template-m{M}.

    Strategy:
      - copy every entry under template_dir EXCEPT `code` and `data`
      - symlink code -> ../../code, data -> ../../data
      - drop in TASK.md from the idea source
      - create final-model/.gitkeep and out/.gitkeep
    """
    agent_dir.mkdir(parents=True, exist_ok=False)
    for entry in template_dir.iterdir():
        if entry.name in ("code", "data"):
            continue
        dst = agent_dir / entry.name
        if entry.is_dir() and not entry.is_symlink():
            shutil.copytree(entry, dst, symlinks=True)
        else:
            shutil.copy2(entry, dst, follow_symlinks=False)
    (agent_dir / "code").symlink_to("../../code")
    (agent_dir / "data").symlink_to("../../data")
    for sub in ("final-model", "out"):
        d = agent_dir / sub
        d.mkdir(exist_ok=True)
        gk = d / ".gitkeep"
        if not gk.exists():
            gk.touch()
    shutil.copy2(task_md, agent_dir / "TASK.md")


def write_task(agent_dir: Path, task_md: Path) -> None:
    shutil.copy2(task_md, agent_dir / "TASK.md")


def slot_template_block(launch_cfg: dict) -> dict:
    """Pick the per-module fields we replay onto each selected slot."""
    if not launch_cfg.get("modules"):
        fail("launch-config has no modules to use as a slot template")
    first = launch_cfg["modules"][0]
    return {
        "harness_components_present": first["harness_components_present"],
        "task_relative_path": first.get("task_relative_path", "TASK.md"),
        "time_budget_minutes": first.get("time_budget_minutes", 45),
    }


def compose_modules(
    selected: list[Path], module: int, slot_template: dict
) -> list[dict]:
    out = []
    for agent_dir in selected:
        name = agent_dir.name  # agent-NN
        out.append(
            {
                "module_name": f"module-{module}-{name}",
                "module_path": str(agent_dir),
                "harness_components_present": slot_template[
                    "harness_components_present"
                ],
                "task_relative_path": slot_template["task_relative_path"],
                "time_budget_minutes": slot_template["time_budget_minutes"],
            }
        )
    return out


def update_launch_config_inventory(
    launch_config_path: Path,
    new_entries: list[dict],
) -> None:
    """Append new slot entries to the canonical launch-configs JSON
    so it remains an accurate inventory of all agent-* folders."""
    cfg = json.loads(launch_config_path.read_text())
    existing_paths = {m["module_path"] for m in cfg.get("modules", [])}
    appended = 0
    for entry in new_entries:
        if entry["module_path"] in existing_paths:
            continue
        cfg["modules"].append(entry)
        appended += 1
    if appended:
        launch_config_path.write_text(json.dumps(cfg, indent=2) + "\n")
    return appended


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--module", type=int, required=True, help="1..4")
    p.add_argument("--idea", type=int, required=True, help="e.g. 1 for idea-01")
    p.add_argument("--count", type=int, required=True, help="agents to launch")
    p.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="webinar-AI root (default: inferred)",
    )
    args = p.parse_args()

    if args.count < 1:
        fail("--count must be >= 1")

    repo_root: Path = args.repo_root.resolve()
    module_dir = repo_root / f"module-{args.module}"
    template_dir = repo_root / f"webinar-meta/env-template-m{args.module}"
    launch_cfg_path = (
        repo_root
        / f"webinar-meta/launch-configs/m{args.module}-idea-{args.idea:02d}.json"
    )
    challenges_dir = repo_root / "webinar-meta/engineering-challenges"
    cohort_dir = repo_root / "cohort-runs"
    out_cfg = cohort_dir / ".launch-config.json"

    for needed, label in [
        (module_dir, f"module-{args.module}/"),
        (template_dir, f"webinar-meta/env-template-m{args.module}/"),
        (launch_cfg_path, str(launch_cfg_path.relative_to(repo_root))),
        (challenges_dir, "webinar-meta/engineering-challenges/"),
    ]:
        if not needed.exists():
            fail(f"missing {label}")

    task_md = find_task_source(challenges_dir, args.idea)
    launch_cfg = json.loads(launch_cfg_path.read_text())
    slot_template = slot_template_block(launch_cfg)

    slots = existing_slots(module_dir)
    fresh_existing = [d for _, d in slots if is_fresh(d)]
    used = [d for _, d in slots if not is_fresh(d)]

    print(
        f"module-{args.module}: {len(slots)} existing slots "
        f"({len(fresh_existing)} fresh, {len(used)} used)"
    )

    selected: list[Path] = []
    # 1) consume fresh existing slots (in order)
    for d in fresh_existing[: args.count]:
        write_task(d, task_md)
        selected.append(d)

    # 2) mint new ones if needed
    needed = args.count - len(selected)
    minted: list[Path] = []
    if needed > 0:
        existing_indices = [n for n, _ in slots]
        for _ in range(needed):
            name = next_agent_name(existing_indices)
            new_dir = module_dir / name
            mint_slot(new_dir, template_dir, task_md)
            existing_indices.append(int(name.split("-")[1]))
            selected.append(new_dir)
            minted.append(new_dir)

    print(f"  reused fresh: {[d.name for d in selected[:len(fresh_existing[: args.count])]]}")
    print(f"  minted new : {[d.name for d in minted]}")

    modules_block = compose_modules(selected, args.module, slot_template)

    # Inventory: append any newly-minted slots back to launch-configs JSON.
    if minted:
        appended = update_launch_config_inventory(
            launch_cfg_path,
            compose_modules(minted, args.module, slot_template),
        )
        if appended:
            print(
                f"  inventory : appended {appended} entries to "
                f"{launch_cfg_path.relative_to(repo_root)}"
            )

    # Write the per-launch config the orchestrator will read.
    cohort_dir.mkdir(parents=True, exist_ok=True)
    out_cfg.write_text(
        json.dumps(
            {
                "angle_name": f"module-{args.module}-idea-{args.idea:02d}",
                "extra_forbidden": launch_cfg["extra_forbidden"],
                "modules": modules_block,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"  wrote      : {out_cfg.relative_to(repo_root)} ({len(modules_block)} slots)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
