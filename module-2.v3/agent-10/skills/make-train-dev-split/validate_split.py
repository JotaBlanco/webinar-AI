"""Validate a (train_paths, dev_paths) split — flag the bugs that bite.

Use this right after calling `split(...)` to confirm the partition is
honest. Returns a dict of findings; raises ValueError on hard violations.

Hard violations (raise):
- A route appears in both train and dev (route leakage).
- A path appears in both lists.
- A path is duplicated within either list.

Warnings (returned, do not raise):
- Dev fraction far from the requested target (>20% off).
- A platform contributes zero segments to one side (when it has any).
- A platform is wildly imbalanced (any side has < 5% of that platform's segments).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path


def _parse_route_key(path: Path) -> tuple[str, str, str]:
    parts = path.parts
    if len(parts) < 5 or parts[-1] != "sim.csv":
        raise ValueError(f"Path does not match expected schema: {path}")
    platform, device, route, _idx, _leaf = parts[-5:]
    return platform, device, route


def validate_split(
    train_paths: list[Path],
    dev_paths: list[Path],
    target_dev_fraction: float | None = None,
    raise_on_hard: bool = True,
) -> dict:
    """Validate a route-grouped train/dev partition.

    Args:
        train_paths, dev_paths: path lists returned by split().
        target_dev_fraction: if given, compare to actual dev fraction.
        raise_on_hard: when True (default), raise ValueError on hard violations.
            Set False if you want the dict of findings for inspection.

    Returns:
        dict with keys:
          n_train, n_dev, dev_fraction,
          route_leaks: list of (platform, device, route) appearing on both sides,
          path_collisions: set of paths in both lists,
          train_duplicates, dev_duplicates: lists of repeated paths,
          per_platform: {platform: {n_train, n_dev, train_frac, dev_frac}},
          warnings: list of human-readable warning strings,
          hard_violations: list of human-readable hard-violation strings.
    """
    train_paths = [Path(p) for p in train_paths]
    dev_paths   = [Path(p) for p in dev_paths]

    findings: dict = {
        "n_train":         len(train_paths),
        "n_dev":           len(dev_paths),
        "dev_fraction":    len(dev_paths) / max(len(train_paths) + len(dev_paths), 1),
        "route_leaks":     [],
        "path_collisions": set(),
        "train_duplicates": [],
        "dev_duplicates":  [],
        "per_platform":    {},
        "warnings":        [],
        "hard_violations": [],
    }

    # Path-level duplicates.
    train_set = set(train_paths)
    dev_set   = set(dev_paths)
    findings["path_collisions"] = train_set & dev_set
    findings["train_duplicates"] = [p for p, c in Counter(train_paths).items() if c > 1]
    findings["dev_duplicates"]   = [p for p, c in Counter(dev_paths).items()   if c > 1]

    # Route leakage.
    train_routes = {_parse_route_key(p) for p in train_paths}
    dev_routes   = {_parse_route_key(p) for p in dev_paths}
    leaks = sorted(train_routes & dev_routes)
    findings["route_leaks"] = leaks

    # Per-platform counts.
    platforms: dict[str, dict[str, int]] = defaultdict(lambda: {"n_train": 0, "n_dev": 0})
    for p in train_paths:
        platforms[_parse_route_key(p)[0]]["n_train"] += 1
    for p in dev_paths:
        platforms[_parse_route_key(p)[0]]["n_dev"] += 1
    for plat, counts in platforms.items():
        total = counts["n_train"] + counts["n_dev"]
        findings["per_platform"][plat] = {
            "n_train":    counts["n_train"],
            "n_dev":      counts["n_dev"],
            "train_frac": counts["n_train"] / total if total else 0.0,
            "dev_frac":   counts["n_dev"]   / total if total else 0.0,
        }

    # Hard violations.
    if leaks:
        findings["hard_violations"].append(
            f"route leakage: {len(leaks)} route(s) appear in both train and dev "
            f"(e.g. {leaks[0]})"
        )
    if findings["path_collisions"]:
        findings["hard_violations"].append(
            f"path collisions: {len(findings['path_collisions'])} path(s) in both lists"
        )
    if findings["train_duplicates"]:
        findings["hard_violations"].append(
            f"train_duplicates: {len(findings['train_duplicates'])} repeated path(s) in train"
        )
    if findings["dev_duplicates"]:
        findings["hard_violations"].append(
            f"dev_duplicates: {len(findings['dev_duplicates'])} repeated path(s) in dev"
        )

    # Soft warnings.
    if target_dev_fraction is not None:
        delta = abs(findings["dev_fraction"] - target_dev_fraction)
        if delta > 0.2 * target_dev_fraction:
            findings["warnings"].append(
                f"dev_fraction is {findings['dev_fraction']:.3f}, target was "
                f"{target_dev_fraction:.3f} — off by {delta / max(target_dev_fraction, 1e-9):.0%}"
            )
    for plat, m in findings["per_platform"].items():
        if m["n_train"] == 0 or m["n_dev"] == 0:
            findings["warnings"].append(
                f"platform `{plat}` has zero on one side "
                f"(train={m['n_train']}, dev={m['n_dev']}) — stratify_by_platform?"
            )
        elif m["dev_frac"] < 0.05 or m["train_frac"] < 0.05:
            findings["warnings"].append(
                f"platform `{plat}` is imbalanced "
                f"(train_frac={m['train_frac']:.2f}, dev_frac={m['dev_frac']:.2f})"
            )

    if raise_on_hard and findings["hard_violations"]:
        raise ValueError(
            "validate_split — hard violations:\n  - "
            + "\n  - ".join(findings["hard_violations"])
        )
    return findings


def format_findings(findings: dict) -> str:
    L = []
    L.append(f"## validate_split — n_train={findings['n_train']}, n_dev={findings['n_dev']}, dev_fraction={findings['dev_fraction']:.3f}")
    if findings["hard_violations"]:
        L.append("### HARD violations")
        for v in findings["hard_violations"]:
            L.append(f"- {v}")
    else:
        L.append("### hard violations: NONE")
    if findings["warnings"]:
        L.append("### warnings")
        for w in findings["warnings"]:
            L.append(f"- {w}")
    else:
        L.append("### warnings: NONE")
    L.append("### per platform")
    L.append("| platform | n_train | n_dev | dev_frac |")
    L.append("|---|---|---|---|")
    for plat, m in findings["per_platform"].items():
        L.append(f"| `{plat}` | {m['n_train']} | {m['n_dev']} | {m['dev_frac']:.2f} |")
    return "\n".join(L)


__all__ = ["validate_split", "format_findings"]
