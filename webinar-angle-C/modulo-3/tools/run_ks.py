"""Thin wrapper around code/generate_simdata_ford.py.

Usage:
    python tools/run_ks.py                          # both Ford platforms, default output dir
    python tools/run_ks.py FORD_MUSTANG_MACH_E_MK1  # one platform

Note: code/generate_simdata_ford.py writes outputs into data/sim/. If you need
per-module isolation, copy the script into your module's out/ and edit the
output path, or pipe its results elsewhere.
"""
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "code" / "generate_simdata_ford.py"


def main():
    args = [sys.executable, str(SCRIPT)] + sys.argv[1:]
    print(f"$ {' '.join(args)}")
    subprocess.run(args, check=False, cwd=ROOT)


if __name__ == "__main__":
    main()
