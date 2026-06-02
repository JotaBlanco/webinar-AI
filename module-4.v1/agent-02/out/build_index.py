"""Walk data/sim/segments and data/sim-only/segments, find all sim.csv files,
group by platform, dump a CSV index."""
from __future__ import annotations
import csv
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-02/data")
OUT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-02/out")

def index(view: str) -> list[dict]:
    rows = []
    for p in sorted((ROOT / view / "segments").rglob("sim.csv")):
        rel = p.relative_to(ROOT / view / "segments")
        platform = rel.parts[0]
        route = rel.parts[1] if len(rel.parts) > 1 else ""
        rows.append({"view": view, "platform": platform, "route": route,
                     "path": str(p), "rel": str(rel)})
    return rows

if __name__ == "__main__":
    rows_sim = index("sim")
    rows_simonly = index("sim-only")
    print(f"sim: {len(rows_sim)}, sim-only: {len(rows_simonly)}")
    with (OUT / "index_sim.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["view","platform","route","path","rel"])
        w.writeheader()
        w.writerows(rows_sim)
    with (OUT / "index_simonly.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["view","platform","route","path","rel"])
        w.writeheader()
        w.writerows(rows_simonly)
