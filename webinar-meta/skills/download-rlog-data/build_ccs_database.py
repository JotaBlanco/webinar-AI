#!/usr/bin/env python3
"""Fetch /tmp/ccs_database.json — the segment index every fetcher reads.

The upstream dataset publishes the same manifest as a top-level file:
    https://huggingface.co/datasets/commaai/commaCarSegments/resolve/main/database.json

It's a JSON dict {platform: [<device>/<route>/<idx>/s, ...]} covering all
~230 platforms (~9 MB). We just download it and drop it at /tmp/ccs_database.json.

Usage:
    python build_ccs_database.py              # download (no overwrite if fresh)
    python build_ccs_database.py --force      # download even if file exists
    python build_ccs_database.py --list-platforms
    python build_ccs_database.py --inspect HYUNDAI_IONIQ_5
"""

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

DB_PATH = Path("/tmp/ccs_database.json")
UPSTREAM = "https://huggingface.co/datasets/commaai/commaCarSegments/resolve/main/database.json"
USER_AGENT = "kb003-db-builder/2.0"


def download(force: bool):
    if DB_PATH.exists() and not force:
        print(f"[skip] {DB_PATH} already exists. Use --force to refresh.")
        return False
    print(f"[get] {UPSTREAM}")
    t0 = time.time()
    req = urllib.request.Request(UPSTREAM, headers={"User-Agent": USER_AGENT})
    tmp = DB_PATH.with_suffix(".json.part")
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)
    # Sanity-check structure before swapping in.
    db = json.loads(tmp.read_text())
    if not isinstance(db, dict) or not db:
        sys.exit("Downloaded file is not the expected {platform: [...]} dict.")
    tmp.rename(DB_PATH)
    mb = DB_PATH.stat().st_size / 1024 / 1024
    total_segs = sum(len(v) for v in db.values())
    print(f"[ok] wrote {DB_PATH} ({mb:.1f} MB, {len(db)} platforms, "
          f"{total_segs} segments, {time.time()-t0:.1f}s)")
    return True


def load_db():
    if not DB_PATH.exists():
        sys.exit(f"Missing {DB_PATH}. Run without arguments to download.")
    return json.loads(DB_PATH.read_text())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="Re-download even if /tmp/ccs_database.json exists.")
    ap.add_argument("--list-platforms", action="store_true", help="Print every platform name (sorted).")
    ap.add_argument("--inspect", metavar="PLATFORM", help="Print segment-count + a few sample paths for one platform.")
    args = ap.parse_args()

    if args.list_platforms or args.inspect:
        db = load_db()
    else:
        download(force=args.force)
        return

    if args.list_platforms:
        for p in sorted(db.keys()):
            print(f"{p:40s}  {len(db[p]):>6d} segments")

    if args.inspect:
        if args.inspect not in db:
            sys.exit(f"Platform {args.inspect!r} not in {DB_PATH}.")
        segs = db[args.inspect]
        print(f"{args.inspect}: {len(segs)} segments")
        for s in segs[:5]:
            print(f"  {s}")
        if len(segs) > 5:
            print(f"  … +{len(segs) - 5} more")


if __name__ == "__main__":
    main()
