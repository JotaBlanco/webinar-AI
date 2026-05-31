"""Render cohort.pdf from cohort.print.html via weasyprint.

Run after report_html.py has produced cohort.print.html. We use the print version
(static SVG charts, no plotly.js) because weasyprint cannot execute JavaScript.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--grade-dir", type=Path, required=True)
    args = p.parse_args()

    print_html = args.grade_dir / "cohort.print.html"
    if not print_html.is_file():
        sys.exit(f"report_pdf: missing {print_html} — run report_html.py first")

    try:
        from weasyprint import HTML
    except ImportError:
        sys.exit("report_pdf: weasyprint not installed in this Python")

    out_pdf = args.grade_dir / "cohort.pdf"
    HTML(filename=str(print_html)).write_pdf(str(out_pdf))
    print(f"report_pdf: cohort.pdf -> {out_pdf}")


if __name__ == "__main__":
    main()
