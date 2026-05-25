"""Computational sensor for the lateral-fidelity-triage skill.

Parses `report.md` at the module root and scores it against structural and
physical sanity rules. Exit code 0 = pass, 1 = fail. Failures are printed
named (rule_id : explanation) so the agent can patch SKILL.md to engineer
each one out — the *ratchet*.

This file is deterministic. Run it as:

    python evals/lateral_fidelity_eval.py [path/to/report.md]

If no path is given, defaults to `./report.md`.
"""

from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


REPORT_DEFAULT = "report.md"
FIG_DEFAULT = "report.png"
REQUIRED_COLUMNS = (
    "variant",
    "rmse_overall",
    "rmse_straight",
    "rmse_steady",
    "rmse_transient",
    "delta_overall_vs_prev",
    "pct_variance_closed",
)


# ---------- Parse report.md ---------------------------------------------------

@dataclass
class VariantRow:
    raw: dict[str, str]
    variant: str
    rmse_overall: float
    rmse_straight: float
    rmse_steady: float
    rmse_transient: float
    delta_overall_vs_prev: float | None
    pct_variance_closed: float


def _coerce_float(s: str) -> float | None:
    s = s.strip().replace("%", "").replace("+", "").replace(",", "")
    if s in {"", "—", "-", "n/a", "N/A"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_table(md: str) -> list[VariantRow]:
    """Find the first markdown table whose header contains every REQUIRED_COLUMNS keyword."""
    lines = md.splitlines()
    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        header = [c.strip().lower() for c in line.strip().strip("|").split("|")]
        # Loose match: each required column must be a substring of some header cell.
        def norm(s: str) -> str:
            s = s.lower().replace("Δ", "delta").replace("δ", "delta").replace("ψ", "psi")
            s = re.sub(r"[^a-z0-9_]+", "_", s).strip("_")
            return s
        h_norm = [norm(h) for h in header]
        if not all(any(req in cell or cell in req for cell in h_norm) for req in REQUIRED_COLUMNS):
            continue
        # Verified header. Skip the alignment row.
        rows: list[VariantRow] = []
        j = i + 2
        while j < len(lines) and lines[j].strip().startswith("|"):
            cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
            if len(cells) != len(header):
                j += 1
                continue
            raw = dict(zip(h_norm, cells))
            try:
                row = VariantRow(
                    raw=raw,
                    variant=_get(raw, "variant"),
                    rmse_overall=_must_float(raw, "rmse_overall"),
                    rmse_straight=_must_float(raw, "rmse_straight"),
                    rmse_steady=_must_float(raw, "rmse_steady"),
                    rmse_transient=_must_float(raw, "rmse_transient"),
                    delta_overall_vs_prev=_coerce_float(_get(raw, "delta_overall_vs_prev")),
                    pct_variance_closed=_must_float(raw, "pct_variance_closed"),
                )
                rows.append(row)
            except (KeyError, ValueError):
                pass
            j += 1
        return rows
    return []


def _get(raw: dict[str, str], key_substr: str) -> str:
    for k, v in raw.items():
        if key_substr in k:
            return v
    raise KeyError(key_substr)


def _must_float(raw: dict[str, str], key_substr: str) -> float:
    v = _coerce_float(_get(raw, key_substr))
    if v is None or math.isnan(v):
        raise ValueError(key_substr)
    return v


# ---------- Rules -------------------------------------------------------------

@dataclass
class Findings:
    failures: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[tuple[str, str]] = field(default_factory=list)

    def fail(self, rule: str, why: str) -> None:
        self.failures.append((rule, why))

    def warn(self, rule: str, why: str) -> None:
        self.warnings.append((rule, why))


def evaluate(md: str, root: Path) -> Findings:
    f = Findings()

    # --- structural ---
    if "report.png" not in md.lower() and "![" not in md:
        f.fail("figure_reference_missing", "report.md does not reference report.png")
    if not (root / FIG_DEFAULT).exists():
        f.fail("figure_file_missing", f"{FIG_DEFAULT} does not exist in module root")
    if "regime" not in md.lower():
        f.fail("regime_thresholds_missing", "report.md does not document regime thresholds")
    if "segment" not in md.lower():
        f.fail("segment_list_missing", "report.md does not list the segments used")

    rows = parse_table(md)
    if not rows:
        f.fail("attribution_table_missing",
               "could not find a markdown table containing every required column "
               + ", ".join(REQUIRED_COLUMNS))
        return f

    if len(rows) < 2:
        f.fail("only_baseline_present",
               f"attribution table has {len(rows)} row(s); need baseline + ≥1 upgrade")

    # --- physical sanity ---
    for r in rows:
        for col, val in (
            ("rmse_overall", r.rmse_overall),
            ("rmse_straight", r.rmse_straight),
            ("rmse_steady", r.rmse_steady),
            ("rmse_transient", r.rmse_transient),
        ):
            if val < 0:
                f.fail("rmse_negative", f"{r.variant}: {col} = {val} (RMSE cannot be negative)")
            if val > 5.0:
                f.fail("rmse_unphysical",
                       f"{r.variant}: {col} = {val} rad/s — yaw-rate RMSE on a passenger car "
                       "should not exceed a few rad/s; units error suspected")

    # baseline must be first and called out
    baseline = rows[0]
    if not re.search(r"\b(V0|baseline|KS\s*baseline)\b", baseline.variant, re.IGNORECASE):
        f.fail("baseline_not_first", f"first row is '{baseline.variant}', expected V0/baseline")
    if abs(baseline.pct_variance_closed) > 1e-3:
        f.fail("baseline_variance_not_zero",
               f"baseline pct_variance_closed = {baseline.pct_variance_closed} (must be 0 by definition)")

    # monotonicity (soft): overall RMSE should generally improve; allow regressions only if
    # the agent explicitly explains them in the narrative.
    for prev, cur in zip(rows, rows[1:]):
        if cur.delta_overall_vs_prev is None:
            f.fail("delta_missing",
                   f"{cur.variant}: Δ_overall_vs_prev is missing")
            continue
        # delta should equal cur.rmse_overall - prev.rmse_overall to 0.01
        expected = cur.rmse_overall - prev.rmse_overall
        if abs(cur.delta_overall_vs_prev - expected) > 0.01:
            f.fail("delta_inconsistent",
                   f"{cur.variant}: Δ = {cur.delta_overall_vs_prev:+.4f} but "
                   f"RMSE diff = {expected:+.4f} (table is internally inconsistent)")
        if cur.delta_overall_vs_prev > 0.005:
            f.warn("monotonicity_violated",
                   f"{cur.variant}: Δ = {cur.delta_overall_vs_prev:+.4f} (got worse vs prev). "
                   "Acceptable only if narrative explains it.")

    # variance closed bookkeeping
    for r in rows[1:]:
        if r.pct_variance_closed < -50:
            f.fail("variance_blew_up",
                   f"{r.variant}: pct_variance_closed = {r.pct_variance_closed:.1f}% — "
                   "this addition is degrading the model, suspect a bug")
        if r.pct_variance_closed > 100.0 + 1e-6:
            f.fail("variance_closed_above_100",
                   f"{r.variant}: pct_variance_closed = {r.pct_variance_closed:.1f}% > 100% — impossible")

    # transient regime sanity: ST/C_α should not catastrophically worsen transient vs baseline.
    for r in rows[1:]:
        if r.rmse_transient > 2.0 * baseline.rmse_transient and r.rmse_transient > 0.05:
            f.fail("transient_worse_than_baseline_without_explanation",
                   f"{r.variant}: transient RMSE {r.rmse_transient:.4f} > 2× baseline "
                   f"({baseline.rmse_transient:.4f}). Either narrative explains this or the variant is buggy.")

    # narrative present
    if "narrative" not in md.lower() and "most-impactful" not in md.lower() and "most impactful" not in md.lower():
        # softer check: at least look for a closing prose section
        last_chunk = md.split("|")[-1].strip()
        if len(last_chunk) < 80:
            f.fail("narrative_missing",
                   "no closing narrative naming the most-impactful addition")

    return f


# ---------- Driver ------------------------------------------------------------

def main(argv: list[str]) -> int:
    root = Path(".").resolve()
    report_path = Path(argv[1]) if len(argv) > 1 else root / REPORT_DEFAULT
    if not report_path.exists():
        print(f"FAIL  report_missing: {report_path} does not exist")
        return 1

    md = report_path.read_text()
    findings = evaluate(md, root)

    for rule, why in findings.failures:
        print(f"FAIL  {rule}: {why}")
    for rule, why in findings.warnings:
        print(f"WARN  {rule}: {why}")

    if findings.failures:
        print(f"\n{len(findings.failures)} failure(s), {len(findings.warnings)} warning(s).")
        return 1
    print(f"\nPASS  (0 failures, {len(findings.warnings)} warning(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
