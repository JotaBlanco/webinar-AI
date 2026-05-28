"""Example tool used by the hello-world skill. Replace with your domain tools.

The agent reads the docstring below as the tool description — keep it accurate.
"""
from __future__ import annotations

import csv
import statistics
from pathlib import Path


def compute_stats(file_path: str) -> dict:
    """Compute mean, median, stdev, and >2σ outliers for a single-column numeric CSV.

    The file must have a header row and a single numeric column. Returns a dict with
    keys: mean, median, stdev, outliers (list of (row_index, value) tuples for any
    value more than 2 standard deviations from the mean). 2σ rather than 3σ because
    for small samples one large outlier inflates its own σ and a strict 3σ rule misses it.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"data file not found: {file_path}")

    values: list[float] = []
    with path.open() as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            if not row:
                continue
            values.append(float(row[0]))

    if len(values) < 2:
        raise ValueError(f"need at least 2 values, got {len(values)}")

    mean = statistics.mean(values)
    median = statistics.median(values)
    stdev = statistics.stdev(values)
    outliers = [
        (i, v) for i, v in enumerate(values) if abs(v - mean) > 2 * stdev
    ]

    return {
        "mean": mean,
        "median": median,
        "stdev": stdev,
        "outliers": outliers,
        "n": len(values),
    }


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 2:
        print("usage: example_tool.py <path-to-csv>")
        sys.exit(2)
    print(json.dumps(compute_stats(sys.argv[1]), indent=2))
