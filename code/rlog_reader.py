"""Lightweight rlog reader — Path B from ../adapters.md.

Decompresses .zst, then iterates capnp Event messages, yielding decoded
(logMonoTime, service, payload) tuples.

Depends on:
  - zstandard (pip)
  - pycapnp    (pip — needs capnp system lib; brew install capnp on macOS)
  - cereal schema pinned in _schema/cereal/  (see _schema/cereal/COMMIT.txt)

If you ever move the _schema directory, set CEREAL_LOG_CAPNP to its log.capnp.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

_HERE = Path(__file__).resolve().parent
_DEFAULT_SCHEMA = _HERE / "_schema" / "cereal" / "log.capnp"


@dataclass
class RlogEvent:
    """One decoded event from a cereal rlog."""
    log_mono_time_ns: int
    service: str
    payload: object   # capnp dynamic reader, service-specific


def _load_schema():
    import capnp
    capnp.remove_import_hook()
    schema_path = Path(os.environ.get("CEREAL_LOG_CAPNP", _DEFAULT_SCHEMA))
    if not schema_path.exists():
        raise FileNotFoundError(
            f"cereal log.capnp not found at {schema_path}. Either restore "
            "_schema/cereal/ or set CEREAL_LOG_CAPNP to a log.capnp path."
        )
    # capnp resolves sibling imports relative to the .capnp file's directory,
    # which is what we want — log.capnp imports car.capnp, custom.capnp,
    # deprecated.capnp, include/c++.capnp all from _schema/cereal/.
    cwd = Path.cwd()
    try:
        os.chdir(schema_path.parent)
        return capnp.load(str(schema_path.name))
    finally:
        os.chdir(cwd)


_LOG_CAPNP = None


def _schema():
    global _LOG_CAPNP
    if _LOG_CAPNP is None:
        _LOG_CAPNP = _load_schema()
    return _LOG_CAPNP


def iter_events(rlog_path: Path) -> Iterator[RlogEvent]:
    """Iterate decoded events from a .zst-compressed rlog."""
    import zstandard

    rlog_path = Path(rlog_path)
    dctx = zstandard.ZstdDecompressor()
    with open(rlog_path, "rb") as f:
        raw = dctx.decompress(f.read(), max_output_size=200_000_000)

    # pycapnp's read_multiple needs a real fileno — go through a tmpfile.
    log_capnp = _schema()
    with tempfile.NamedTemporaryFile() as tmp:
        tmp.write(raw)
        tmp.flush()
        tmp.seek(0)
        for msg in log_capnp.Event.read_multiple(tmp):
            yield RlogEvent(
                log_mono_time_ns=msg.logMonoTime,
                service=msg.which(),
                payload=getattr(msg, msg.which()),
            )


def list_services(rlog_path: Path) -> dict[str, int]:
    """Return {service: event_count} for one rlog. Workshop's first sanity check."""
    counts: dict[str, int] = {}
    for ev in iter_events(rlog_path):
        counts[ev.service] = counts.get(ev.service, 0) + 1
    return counts


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("usage: python rlog_reader.py <path/to/rlog.zst>")
        sys.exit(2)
    counts = list_services(Path(sys.argv[1]))
    print(f"{sum(counts.values())} events across {len(counts)} services:")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:30s} {v:6d}")
