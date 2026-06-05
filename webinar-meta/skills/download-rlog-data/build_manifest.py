#!/usr/bin/env python3
"""Build manifest.json for a downloaded platform under data/raw/segments/<PLATFORM>/.

Walks the on-disk tree and writes totals + a device/route/segment tree to
manifest.json inside the platform folder.

Usage:
    python build_manifest.py FORD_EXPLORER_MK6
    python build_manifest.py HYUNDAI_IONIQ_5 --root /custom/repo
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def repo_root_from_skill() -> Path:
    return Path(__file__).resolve().parents[3]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("platform")
    ap.add_argument("--root", type=Path, default=None,
                    help="Repo root. Defaults to the webinar-AI root inferred from this script's path.")
    args = ap.parse_args()

    root = (args.root or repo_root_from_skill()).resolve()
    raw_root = root / "data" / "raw"
    plat_dir = raw_root / "segments" / args.platform
    if not plat_dir.exists():
        sys.exit(f"Missing {plat_dir} — download it first with fetch_platform.py {args.platform}")

    devices = {}
    total_bytes = total_segments = total_routes = 0

    for device_dir in sorted(p for p in plat_dir.iterdir() if p.is_dir()):
        routes = {}
        d_segs = 0
        for route_dir in sorted(p for p in device_dir.iterdir() if p.is_dir()):
            segs = []
            for idx_dir in sorted(
                (p for p in route_dir.iterdir() if p.is_dir()),
                key=lambda p: int(p.name) if p.name.isdigit() else p.name,
            ):
                rlog = idx_dir / "rlog.zst"
                if not rlog.exists():
                    continue
                size = rlog.stat().st_size
                segs.append({
                    "idx": idx_dir.name,
                    "bytes": size,
                    "path": rlog.relative_to(raw_root).as_posix(),
                })
                total_bytes += size
            if not segs:
                continue
            routes[route_dir.name] = {
                "segments": segs,
                "segment_count": len(segs),
                "duration_minutes_approx": len(segs),  # 1 segment ≈ 1 minute
            }
            d_segs += len(segs)
            total_routes += 1
        if not routes:
            continue
        devices[device_dir.name] = {
            "routes": routes,
            "route_count": len(routes),
            "segment_count": d_segs,
        }
        total_segments += d_segs

    manifest = {
        "platform": args.platform,
        "source": {
            "dataset": "commaai/commaCarSegments",
            "ref": "main",
            "license": "MIT",
            "homepage": "https://huggingface.co/datasets/commaai/commaCarSegments",
            "segment_url_pattern": "https://huggingface.co/datasets/commaai/commaCarSegments/resolve/main/segments/<device>/<route>/<idx>/rlog.zst",
        },
        "format": {
            "file": "rlog.zst",
            "description": "zstandard-compressed openpilot cereal log",
            "reader": "openpilot.tools.lib.logreader.LogReader",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "totals": {
            "devices": len(devices),
            "routes": total_routes,
            "segments": total_segments,
            "bytes": total_bytes,
            "gigabytes": round(total_bytes / 1024**3, 3),
            "duration_minutes_approx": total_segments,
            "duration_hours_approx": round(total_segments / 60, 2),
        },
        "devices": devices,
    }

    out = plat_dir / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2))
    print(f"[ok] wrote {out}")
    print(json.dumps(manifest["totals"], indent=2))


if __name__ == "__main__":
    main()
