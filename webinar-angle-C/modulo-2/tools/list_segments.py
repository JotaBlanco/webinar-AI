"""List available data segments by platform.

Usage:
    python tools/list_segments.py                          # all platforms, sim
    python tools/list_segments.py FORD_MUSTANG_MACH_E_MK1  # one platform, sim
    python tools/list_segments.py FORD_F_150_LIGHTNING_MK1 raw  # raw rlogs
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def main():
    platform = sys.argv[1] if len(sys.argv) > 1 else None
    kind = sys.argv[2] if len(sys.argv) > 2 else "sim"
    base = DATA / kind / "segments"
    if not base.exists():
        print(f"No such dir: {base}", file=sys.stderr)
        sys.exit(1)
    platforms = [platform] if platform else sorted(p.name for p in base.iterdir() if p.is_dir())
    for plat in platforms:
        pdir = base / plat
        if not pdir.exists():
            print(f"# {plat}: missing")
            continue
        ext = "sim.csv" if kind == "sim" else "rlog.zst"
        files = sorted(pdir.rglob(ext))
        print(f"# {plat}: {len(files)} {ext}")
        for f in files[:20]:
            print(f.relative_to(DATA))
        if len(files) > 20:
            print(f"... ({len(files) - 20} more)")


if __name__ == "__main__":
    main()
