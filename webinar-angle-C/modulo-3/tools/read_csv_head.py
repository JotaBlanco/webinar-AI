"""Read the first N rows of a CSV (default 5). Prints columns + sample.

Usage:
    python tools/read_csv_head.py <path-to-csv> [n_rows]
"""
import sys
from pathlib import Path
import pandas as pd


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    path = Path(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    df = pd.read_csv(path, nrows=n)
    print(f"# {path}")
    print(f"# columns ({len(df.columns)}): {', '.join(df.columns)}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
