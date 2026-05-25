# tools/ (módulo 1)

Three thin wrappers. Call them with `python tools/<name>.py`.

- `list_segments.py` — list available data segments by platform.
- `read_csv_head.py` — peek at a CSV's columns + first rows.
- `run_ks.py` — run `code/generate_simdata_ford.py` (writes to `data/sim/` — see notes inside the script if you need isolation).

If you need more tools, write them. Keep them thin (no logic, just argv → code/).
