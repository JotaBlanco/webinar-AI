"""Workshop's literal first cell: open one rlog, enumerate which services are
present, dump rates and counts.

Becomes runnable as soon as rlog_reader.py is finished (pycapnp + cereal/log.capnp
pin). Until then, this script exists so the next session knows exactly what to
type first.

Usage:
    python inspect_rlog.py <path/to/rlog.zst>
"""

import sys
from pathlib import Path

from rlog_reader import iter_events


def main(rlog_path: Path) -> None:
    counts: dict[str, int] = {}
    t0: int | None = None
    t1: int = 0
    for ev in iter_events(rlog_path):
        if t0 is None:
            t0 = ev.log_mono_time_ns
        t1 = ev.log_mono_time_ns
        counts[ev.service] = counts.get(ev.service, 0) + 1

    if t0 is None:
        print("Empty rlog?")
        return
    duration_s = (t1 - t0) / 1e9
    print(f"Segment: {rlog_path.name}")
    print(f"Duration: {duration_s:.2f} s")
    print(f"Services present ({len(counts)} kinds):")
    for svc, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        hz = n / duration_s if duration_s > 0 else float("nan")
        print(f"  {svc:30s}  {n:6d} events   {hz:6.1f} Hz")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python inspect_rlog.py <path/to/rlog.zst>")
        sys.exit(2)
    main(Path(sys.argv[1]))
