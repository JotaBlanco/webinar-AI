#!/usr/bin/env python3
"""Parallel downloader for one platform of commaai/commaCarSegments.

Two modes:

  Whole-platform (default):
      <data_root>/raw/segments/<PLATFORM>/<dev>/<route>/<idx>/rlog.zst

  Train/val split (--val-split):
      <data_root>/raw/segments/<PLATFORM>/...        ← train pool
      <val_data_root>/raw/segments/<PLATFORM>/...    ← held-out val
      Split strategies (see --split-strategy):
        held-out-devices (default): whole devices go to either train OR val,
            never both. Best generalization test — val measures performance
            on physical cars the agent never saw. Falls back automatically
            to route-grouped if the platform has fewer than 4 devices.
        route-grouped: whole routes go together, route assignment is purely
            random. Same device may appear in both. Matches F1/KB003's
            original behaviour.

  data_root and val_data_root come from webinar-meta/data-paths.json
  (resolved relative to the webinar-AI repo root). Override with --root.

Reads /tmp/ccs_database.json. Build that first with build_ccs_database.py.

Re-runnable: skips any rlog.zst already present with non-zero size.

A split.json describing what went where is written into <val_data_root>/<PLATFORM>/
(and mirrored under <data_root>/raw/segments/<PLATFORM>/) for traceability.

Usage:
    python fetch_platform.py FORD_EXPLORER_MK6
    python fetch_platform.py HYUNDAI_IONIQ_5 --val-split --train 800 --val 400 --seed 42
    python fetch_platform.py HYUNDAI_IONIQ_5 --val-split --split-strategy route-grouped
"""

import argparse
import json
import random
import sys
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("/tmp/ccs_database.json")
BASE_URL = "https://huggingface.co/datasets/commaai/commaCarSegments/resolve/main/segments"
USER_AGENT = "kb003-fetcher/2.0"

DEFAULT_WORKERS = 16
DEFAULT_RETRIES = 4
OVERSHOOT_TOL = 1.05  # allow +5% over a split target to keep device/route boundaries clean
HELD_OUT_MIN_DEVICES = 4  # below this, fall back to route-grouped


def repo_root_from_skill() -> Path:
    """Skill lives at <repo>/webinar-meta/skills/download-rlog-data/."""
    return Path(__file__).resolve().parents[3]


def load_data_paths(repo_root: Path):
    cfg = repo_root / "webinar-meta" / "data-paths.json"
    if not cfg.exists():
        sys.exit(f"Missing {cfg} — declare data_root / val_data_root there.")
    return json.loads(cfg.read_text())


def load_segments(platform: str):
    if not DB_PATH.exists():
        sys.exit(f"Missing {DB_PATH}. Run build_ccs_database.py first.")
    db = json.loads(DB_PATH.read_text())
    if platform not in db:
        sys.exit(f"Platform {platform!r} not in {DB_PATH}. "
                 f"Available: {', '.join(sorted(db.keys())) or '<empty>'}")
    segs = db[platform]
    if not segs:
        sys.exit(f"Platform {platform!r} has zero segments in {DB_PATH}.")
    return segs


def parse(path_str: str):
    parts = path_str.split("/")
    if len(parts) < 3:
        raise ValueError(f"unexpected segment path: {path_str!r}")
    return parts[0], parts[1], parts[2]


def download_one(out_root: Path, dev: str, route: str, idx: str, retries: int):
    tgt = out_root / dev / route / idx / "rlog.zst"
    if tgt.exists() and tgt.stat().st_size > 0:
        return ("skip", tgt.stat().st_size, f"{dev}/{route}/{idx}")
    tgt.parent.mkdir(parents=True, exist_ok=True)
    url = f"{BASE_URL}/{dev}/{route}/{idx}/rlog.zst"
    tmp = tgt.with_suffix(".zst.part")
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
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
            return ("ok", size, f"{dev}/{route}/{idx}")
        except Exception as e:
            last_err = e
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            time.sleep(0.5 * (attempt + 1))
    return ("err", 0, f"{dev}/{route}/{idx} :: {last_err}")


def fetch(label: str, out_root: Path, pairs, workers: int, retries: int, platform: str):
    print(f"\n[{label}] {len(pairs)} segments → {out_root}")
    out_root.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    ok = skip = err = 0
    total_bytes = 0
    errors = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(download_one, out_root, dev, route, idx, retries)
                for (dev, route, idx) in pairs]
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
            if i % 50 == 0 or i == len(pairs):
                el = time.time() - t0
                mb = total_bytes / 1024 / 1024
                rate = mb / el if el > 0 else 0
                print(f"  [{label} {i:4d}/{len(pairs)}] "
                      f"ok={ok} skip={skip} err={err} "
                      f"total={mb:.1f} MB ({rate:.1f} MB/s, {el:.0f}s)")
    if errors:
        log = out_root.parent / f"{platform}.{label}.errors.log"
        log.write_text("\n".join(errors))
        print(f"  [{label} warn] {err} errors written to {log}")
    return ok, skip, err, total_bytes


def _routes_by_device(segs):
    """Return {device: {route: [idx, ...]}}."""
    out = defaultdict(lambda: defaultdict(list))
    for s in segs:
        dev, route, idx = parse(s)
        out[dev][route].append(idx)
    return out


def _flatten(routes_for_device):
    """routes={route: [idx, ...]} → list of (route, idx) pairs."""
    return [(r, i) for r, idxs in routes_for_device.items() for i in idxs]


def plan_held_out_devices(segs, target_train: int, target_val: int, seed: int):
    """Whole devices go either to train or to val, never both.

    Greedy: shuffle device order with seed, assign devices to val until val
    target is hit (within OVERSHOOT_TOL); remaining devices fill train (also
    capped to target_train * OVERSHOOT_TOL). Devices that would push either
    side over the cap are skipped. Returns (train_pairs, val_pairs, meta).
    """
    by_dev = _routes_by_device(segs)
    devices = sorted(by_dev.keys())
    if len(devices) < HELD_OUT_MIN_DEVICES:
        return None  # caller falls back

    rng = random.Random(seed)
    shuffled = devices[:]
    rng.shuffle(shuffled)

    val_devs, train_devs = [], []
    val_n = train_n = 0
    for dev in shuffled:
        n = sum(len(idxs) for idxs in by_dev[dev].values())
        if val_n < target_val:
            if val_n + n <= target_val * OVERSHOOT_TOL:
                val_devs.append(dev)
                val_n += n
                continue
        if train_n + n <= target_train * OVERSHOOT_TOL:
            train_devs.append(dev)
            train_n += n

    train_pairs = [(d, r, i) for d in train_devs for (r, i) in _flatten(by_dev[d])]
    val_pairs   = [(d, r, i) for d in val_devs   for (r, i) in _flatten(by_dev[d])]

    meta = {
        "strategy": "held-out-devices",
        "n_train_devices": len(train_devs),
        "n_val_devices": len(val_devs),
        "held_out_device_ids": sorted(val_devs),
    }
    return train_pairs, val_pairs, meta


def plan_route_grouped(segs, target_train: int, target_val: int, seed: int):
    """Whole routes go together; route assignment is random. Devices may appear
    in both sides. Returns (train_pairs, val_pairs, meta)."""
    routes = defaultdict(list)
    for s in segs:
        dev, route, idx = parse(s)
        routes[(dev, route)].append(idx)

    keys = sorted(routes.keys())
    random.Random(seed).shuffle(keys)

    train_pairs, val_pairs = [], []
    train_n = val_n = 0
    for key in keys:
        n = len(routes[key])
        if train_n < target_train:
            if train_n + n <= target_train * OVERSHOOT_TOL:
                train_pairs.extend((key[0], key[1], idx) for idx in routes[key])
                train_n += n
            continue
        if val_n < target_val:
            if val_n + n <= target_val * OVERSHOOT_TOL:
                val_pairs.extend((key[0], key[1], idx) for idx in routes[key])
                val_n += n

    meta = {
        "strategy": "route-grouped",
        "n_train_devices": len({d for d, _, _ in train_pairs}),
        "n_val_devices": len({d for d, _, _ in val_pairs}),
    }
    return train_pairs, val_pairs, meta


def plan_split(segs, target_train, target_val, seed, strategy):
    if strategy == "held-out-devices":
        result = plan_held_out_devices(segs, target_train, target_val, seed)
        if result is None:
            n_devs = len({parse(s)[0] for s in segs})
            print(f"[note] only {n_devs} devices — falling back to route-grouped split", file=sys.stderr)
            return plan_route_grouped(segs, target_train, target_val, seed)
        return result
    if strategy == "route-grouped":
        return plan_route_grouped(segs, target_train, target_val, seed)
    sys.exit(f"unknown --split-strategy: {strategy!r}")


def write_split_manifest(platform, val_root, train_root, train_pairs, val_pairs, meta, args):
    spec = {
        "platform": platform,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "strategy": meta["strategy"],
        "seed": args.seed,
        "targets": {"train": args.train, "val": args.val, "overshoot_tol": OVERSHOOT_TOL},
        "actual": {
            "train_segments": len(train_pairs),
            "val_segments": len(val_pairs),
            "train_routes": len({(d, r) for d, r, _ in train_pairs}),
            "val_routes": len({(d, r) for d, r, _ in val_pairs}),
            "train_devices": meta.get("n_train_devices"),
            "val_devices": meta.get("n_val_devices"),
        },
    }
    if "held_out_device_ids" in meta:
        spec["held_out_device_ids"] = meta["held_out_device_ids"]

    for root in (val_root, train_root):
        root.mkdir(parents=True, exist_ok=True)
        (root / "split.json").write_text(json.dumps(spec, indent=2))
    print(f"[split] wrote split.json under both train and val roots")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("platform", help="e.g. FORD_EXPLORER_MK6, HYUNDAI_IONIQ_5")
    ap.add_argument("--root", type=Path, default=None,
                    help="Repo root (default: inferred from this script's path).")
    ap.add_argument("--val-split", action="store_true",
                    help="Produce a train + held-out-val split instead of downloading the whole platform.")
    ap.add_argument("--split-strategy", choices=["held-out-devices", "route-grouped"],
                    default="held-out-devices",
                    help="held-out-devices (default): physical cars never appear in both sides. "
                         "route-grouped: random route shuffle (cars can overlap).")
    ap.add_argument("--train", type=int, default=800, help="Target #segments for train split (--val-split only).")
    ap.add_argument("--val", type=int, default=400, help="Target #segments for val split (--val-split only).")
    ap.add_argument("--seed", type=int, default=42, help="Shuffle seed for the split.")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    ap.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    args = ap.parse_args()

    repo_root = (args.root or repo_root_from_skill()).resolve()
    paths = load_data_paths(repo_root)
    data_root = (repo_root / paths["data_root"]).resolve()
    val_data_root = (repo_root / paths["val_data_root"]).resolve()

    segs = load_segments(args.platform)
    train_root = data_root / "raw" / "segments" / args.platform
    val_root = val_data_root / "raw" / "segments" / args.platform

    if not args.val_split:
        pairs = [parse(s) for s in segs]
        print(f"[plan] {args.platform}: {len(pairs)} segments (whole platform)")
        ok, skip, err, total = fetch("all", train_root, pairs, args.workers, args.retries, args.platform)
        print(f"\n[done] ok={ok} skip={skip} err={err}  "
              f"total={total/1024/1024:.1f} MB")
        if err:
            sys.exit(2)
        return

    train_pairs, val_pairs, meta = plan_split(segs, args.train, args.val, args.seed, args.split_strategy)
    n_train_devs = meta.get("n_train_devices", "?")
    n_val_devs = meta.get("n_val_devices", "?")
    print(f"[plan] {args.platform} ({meta['strategy']}, seed={args.seed}): "
          f"train={len(train_pairs)} segs / {n_train_devs} devices, "
          f"val={len(val_pairs)} segs / {n_val_devs} devices "
          f"(targets {args.train}/{args.val})")

    write_split_manifest(args.platform, val_root, train_root, train_pairs, val_pairs, meta, args)

    t_ok, t_skip, t_err, t_bytes = fetch("train", train_root, train_pairs, args.workers, args.retries, args.platform)
    v_ok, v_skip, v_err, v_bytes = fetch("val",   val_root,   val_pairs,   args.workers, args.retries, args.platform)
    total_mb = (t_bytes + v_bytes) / 1024 / 1024
    print(f"\n[done] train: ok={t_ok} skip={t_skip} err={t_err}")
    print(f"       val:   ok={v_ok} skip={v_skip} err={v_err}")
    print(f"       total: {total_mb:.1f} MB across "
          f"{len(train_pairs) + len(val_pairs)} segments")
    if t_err or v_err:
        sys.exit(2)


if __name__ == "__main__":
    main()
