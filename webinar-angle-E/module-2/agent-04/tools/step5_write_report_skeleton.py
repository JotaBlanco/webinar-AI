#!/usr/bin/env python3
"""step5_write_report_skeleton.py — produce REPORT.md skeleton from V0 + V1/V2/V3 JSON files."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


SECTIONS = """\
# REPORT — lateral-fidelity workflow (workshop scaffold S2)

## Platform and contract

- Platform scored: **FILL IN** (e.g., FORD_MUSTANG_MACH_E_MK1).
- `yaw_rate_meas_rads` is measured truth (from rlog IMU, Ford-only).
- Speed `v` and steering `δ` are **clamped** to measured under the speed-known operating contract.

## Variant ladder

{table}

## Attribution

- V0→V1 marginal drop: **FILL IN**
- V1→V2 marginal drop: **FILL IN**
- V2→V3 marginal drop: **FILL IN**
- Sum of marginals vs total V0→V3 drop: **FILL IN** (within 15%? yes/no).

## Regressions and physical reasons

- {regression_line}

## Notes

- FILL IN any constraints or surprises that emerged during the workflow.
"""


def fmt(x, n=5):
    try:
        return f"{x:.{n}f}"
    except (TypeError, ValueError):
        return "—"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rmse-files", nargs="+", type=Path, required=True)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    v0 = None
    v123 = None
    for p in args.rmse_files:
        d = json.loads(p.read_text())
        if "V0_overall" in d:
            v0 = d
        if "V1" in d:
            v123 = d
    if v0 is None or v123 is None:
        print("need both V0 JSON and V1/V2/V3 JSON", file=sys.stderr)
        return 1

    rows = [
        ("V0 (baseline)", v0["V0_overall"], v0["V0_straight"], v0["V0_steady"], v0["V0_transient"]),
        ("V1 (KS recalib + bias)", v123["V1"]["overall"], v123["V1"]["straight"],
         v123["V1"]["steady"], v123["V1"]["transient"]),
        ("V2 (Linear ST, prior Cα)", v123["V2"]["overall"], v123["V2"]["straight"],
         v123["V2"]["steady"], v123["V2"]["transient"]),
        ("V3 (Linear ST, fit Cα)", v123["V3"]["overall"], v123["V3"]["straight"],
         v123["V3"]["steady"], v123["V3"]["transient"]),
    ]
    lines = ["| variant | overall | straight | steady | transient |",
             "|---|---:|---:|---:|---:|"]
    for name, ov, st, sd, tr in rows:
        lines.append(f"| {name} | {fmt(ov)} | {fmt(st)} | {fmt(sd)} | {fmt(tr)} |")
    table = "\n".join(lines)

    pegged = v123.get("V3_fit", {}).get("pegged", False)
    if pegged:
        regression_line = ("V3's Cα fit pegged at the upper bound → flagged as a regression: "
                           "the openpilot ST prior is already stiffer than the tyres want.")
    else:
        regression_line = "no variant regressed past V0; if any per-regime row worsened, name it here and give a physical cause."

    args.out.write_text(SECTIONS.format(table=table, regression_line=regression_line))
    print(f"skeleton → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
