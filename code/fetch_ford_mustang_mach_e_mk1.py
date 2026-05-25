#!/usr/bin/env python3
"""Parallel downloader for FORD_MUSTANG_MACH_E_MK1 segments of commaCarSegments.

Mirrors the upstream layout:
  KB003/data/segments/FORD_MUSTANG_MACH_E_MK1/<device>/<route>/<idx>/rlog.zst

Re-runnable: skips files already present with non-zero size.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
DB_PATH = "/tmp/ccs_database.json"
ROOT = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT_DIR = ROOT / "segments" / PLATFORM
BASE_URL = "https://huggingface.co/datasets/commaai/commaCarSegments/resolve/main/segments"
WORKERS = 16
RETRIES = 4


def load_segments():
    with open(DB_PATH) as f:
        db = json.load(f)
    if PLATFORM not in db:
        sys.exit(f"Platform {PLATFORM} not found in database.json")
    return db[PLATFORM]


def parse(path_str):
    parts = path_str.split("/")
    if len(parts) < 3:
        raise ValueError(path_str)
    device, route, idx = parts[0], parts[1], parts[2]
    return device, route, idx


def target_for(device, route, idx):
    return OUT_DIR / device / route / idx / "rlog.zst"


def download_one(seg):
    device, route, idx = parse(seg)
    tgt = target_for(device, route, idx)
    if tgt.exists() and tgt.stat().st_size > 0:
        return ("skip", tgt.stat().st_size, seg)
    tgt.parent.mkdir(parents=True, exist_ok=True)
    url = f"{BASE_URL}/{device}/{route}/{idx}/rlog.zst"
    tmp = tgt.with_suffix(".zst.part")
    last_err = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "kb003-fetcher/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
                while True:
                    chunk = r.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            size = tmp.stat().st_size
            if size == 0:
                raise RuntimeError("zero-byte download")
            tmp.rename(tgt)
            return ("ok", size, seg)
        except Exception as e:
            last_err = e
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            time.sleep(0.5 * (attempt + 1))
    return ("err", 0, f"{seg} :: {last_err}")


def main():
    segs = load_segments()
    print(f"[plan] {PLATFORM}: {len(segs)} segments")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    ok = skip = err = 0
    total_bytes = 0
    errors = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(download_one, s) for s in segs]
        for i, fut in enumerate(as_completed(futs), 1):
            status, size, info = fut.result()
            if status == "ok":
                ok += 1
                total_bytes += size
            elif status == "skip":
                skip += 1
                total_bytes += size
            else:
                err += 1
                errors.append(info)
            if i % 25 == 0 or i == len(segs):
                el = time.time() - t0
                mb = total_bytes / 1024 / 1024
                rate = mb / el if el > 0 else 0
                print(
                    f"[{i:4d}/{len(segs)}] ok={ok} skip={skip} err={err} "
                    f"total={mb:.1f} MB ({rate:.1f} MB/s, {el:.0f}s)"
                )

    print(f"\n[done] ok={ok} skip={skip} err={err}  total={total_bytes/1024/1024:.1f} MB  elapsed={time.time()-t0:.0f}s")
    if errors:
        err_log = OUT_DIR.parent / f"{PLATFORM}.errors.log"
        with open(err_log, "w") as f:
            f.write("\n".join(errors))
        print(f"[warn] {err} errors written to {err_log}")
        sys.exit(2)


if __name__ == "__main__":
    main()
