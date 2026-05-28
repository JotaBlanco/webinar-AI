#!/usr/bin/env python3
"""lateral_fidelity_eval.py — computational sensor scoring REPORT.md.

Run:  python3 lateral_fidelity_eval.py REPORT.md

Checks the six workshop success metrics. Exits 0 if all pass, 1 if any fail.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ATTRIBUTION_COHERENCE_THR = 0.15


def find_first_markdown_table(text: str) -> str | None:
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("|") and "|" in lines[i]:
            if i + 1 < len(lines) and re.match(r"^\s*\|[\s\-:|]+\|\s*$", lines[i + 1]):
                start = i
                end = i + 2
                while end < len(lines) and lines[end].strip().startswith("|"):
                    end += 1
                return "\n".join(lines[start:end])
        i += 1
    return None


def _parse_num(s: str) -> float | None:
    cleaned = re.sub(r"[^\d.\-+eE]", "", s)
    if not cleaned or cleaned in {"-", "+", ".", "-.", "+."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def check_truth_channel_correct(text: str) -> tuple[bool, str]:
    if "yaw_rate_meas_rads" not in text and "yaw_rate_meas" not in text:
        return False, "scored channel `yaw_rate_meas_rads` not named in report"
    for m in re.finditer(r"yaw_rate_meas[_a-z]*", text):
        window = text[max(0, m.start() - 200):m.end() + 200].lower()
        if "measure" in window or "truth" in window:
            return True, "channel named and identified as measured/truth"
    return False, "channel named but not identified as measured/truth in nearby context"


def check_contract_acknowledged(text: str) -> tuple[bool, str]:
    has_clamp = bool(re.search(r"clamp", text, re.IGNORECASE))
    has_pred = bool(re.search(r"predict", text, re.IGNORECASE))
    if has_clamp and has_pred:
        return True, "clamp + predict both present"
    if not has_clamp:
        return False, "no mention of clamping anywhere"
    return False, "no mention of prediction alongside clamping"


def check_regime_breakdown(text: str, table: str | None) -> tuple[bool, str]:
    hay = ((table or "") + "\n" + text).lower()
    hits = [r for r in ("straight", "steady", "transient", "cornering") if r in hay]
    if len(hits) >= 3:
        return True, f"regime words present: {hits}"
    return False, f"insufficient regime breakdown (found only {hits})"


def check_methodology_consistent(text: str, table: str | None) -> tuple[bool, str]:
    if not table:
        return False, "no variant table found"
    if re.search(r"same segment|consistent (segment|across|methodology)|segment set|held constant",
                 text, re.IGNORECASE):
        return True, "methodology-consistency statement present"
    return False, "no explicit statement that segment-set/regime-mask is held constant"


def _parse_table(table: str) -> tuple[list[str], list[list[str]]]:
    rows = [r for r in table.splitlines() if r.strip().startswith("|")]
    if len(rows) < 3:
        return [], []
    header = [c.strip() for c in rows[0].strip("|").split("|")]
    data_rows = []
    for r in rows[2:]:
        cells = [c.strip() for c in r.strip("|").split("|")]
        if len(cells) == len(header):
            data_rows.append(cells)
    return header, data_rows


def check_attribution_coherent(table: str | None) -> tuple[bool, str]:
    if not table:
        return False, "no variant table"
    header, data_rows = _parse_table(table)
    if not header or len(data_rows) < 2:
        return False, "variant table too short"

    rmse_idx = None
    delta_idx = None
    for i, h in enumerate(header):
        h_l = h.lower()
        if rmse_idx is None and "rmse" in h_l and ("overall" in h_l or h_l.strip() == "rmse" or "total" in h_l):
            rmse_idx = i
        if delta_idx is None and ("δ" in h or "delta" in h_l or "marginal" in h_l or "drop" in h_l):
            delta_idx = i
    if rmse_idx is None:
        for i in range(len(header)):
            if _parse_num(data_rows[0][i]) is not None:
                rmse_idx = i
                break
    if rmse_idx is None:
        return False, "could not locate an RMSE column"

    rmses = [_parse_num(r[rmse_idx]) for r in data_rows]
    rmses = [v for v in rmses if v is not None]
    if len(rmses) < 2:
        return False, "fewer than 2 numeric RMSE rows"
    total_drop = rmses[0] - rmses[-1]
    if total_drop <= 0:
        return False, f"total drop {total_drop:.5f} is non-positive — no improvement?"

    if delta_idx is not None:
        deltas = [_parse_num(r[delta_idx]) for r in data_rows]
        deltas = [d for d in deltas if d is not None]
        sum_marginal = -sum(deltas) if deltas else 0.0
    else:
        sum_marginal = sum(rmses[i - 1] - rmses[i] for i in range(1, len(rmses)))

    err = abs(sum_marginal - total_drop) / abs(total_drop)
    if err < ATTRIBUTION_COHERENCE_THR:
        return True, f"|Σmarg−total|/total = {err:.3f} < {ATTRIBUTION_COHERENCE_THR}"
    return False, f"|Σmarg−total|/total = {err:.3f} ≥ {ATTRIBUTION_COHERENCE_THR}"


def check_regression_flagged(text: str, table: str | None) -> tuple[bool, str]:
    if not table:
        return False, "no variant table"
    header, data_rows = _parse_table(table)
    if not header or not data_rows:
        return True, "no data rows (vacuous pass)"

    delta_idx = None
    for i, h in enumerate(header):
        if "δ" in h or "delta" in h.lower() or "drop" in h.lower():
            delta_idx = i
            break
    if delta_idx is None:
        return True, "no Δ column (vacuous pass)"

    pos_drop_rows = []
    for r in data_rows:
        v = _parse_num(r[delta_idx])
        if v is not None and v > 0:
            pos_drop_rows.append(r[0])

    if not pos_drop_rows:
        return True, "no regression observed (vacuous pass)"
    if re.search(r"regress|worsen|got worse|made it worse", text, re.IGNORECASE):
        return True, f"regression rows {pos_drop_rows} discussed with cause"
    return False, f"regression rows {pos_drop_rows} not flagged in prose"


def main():
    if len(sys.argv) != 2:
        print("usage: lateral_fidelity_eval.py REPORT.md", file=sys.stderr)
        sys.exit(2)
    report = Path(sys.argv[1])
    if not report.is_file():
        print(f"report not found: {report}", file=sys.stderr)
        sys.exit(2)
    text = report.read_text()
    table = find_first_markdown_table(text)

    results = [
        ("truth-channel-correct",    *check_truth_channel_correct(text)),
        ("contract-acknowledged",    *check_contract_acknowledged(text)),
        ("regime-breakdown-present", *check_regime_breakdown(text, table)),
        ("methodology-consistent",   *check_methodology_consistent(text, table)),
        ("attribution-coherent",     *check_attribution_coherent(table)),
        ("honest-regression-flagged",*check_regression_flagged(text, table)),
    ]

    print(f"Eval results for {report}:")
    failures = 0
    for name, ok, msg in results:
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {name}: {msg}")
        if not ok:
            failures += 1
    n = len(results)
    print(f"\nSummary: {n - failures}/{n} metrics passed, {failures} failed.")
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
