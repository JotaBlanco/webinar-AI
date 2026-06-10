"""Top-level launcher: compare N agents on one segment.

Usage
-----
List every available segment:

    python compare.py list
    python compare.py list --platform TESLA_MODEL_3

Compare agents on a segment (index from `list` or a slug substring):

    python compare.py 5 \\
        --agent module-1/agent-01 \\
        --agent module-3/agent-01:M3-flagship \\
        --html             # default: plotly HTML
    python compare.py 5 --agent ... --rrd        # save .rrd
    python compare.py 5 --agent ... --spawn      # open rerun viewer

Use a saved preset (a JSON file under presets/ — see `presets/example.json`):

    python compare.py 5 --preset cohort-flagship --html
    python compare.py --preset cohort-flagship --html      # segment from preset

Save the current invocation back to a preset for future reuse:

    python compare.py 5 --agent A --agent B --save-preset my-comparison

Notes
-----
- Agent specs are paths under webinar-AI/. The directory must contain
  `final-model/predict.py` (or `predict.py` at the top).
- Add `:label` to override the legend name, e.g.
  `module-1/agent-01:V1 (m1 flagship)`.
- The V0 kinematic baseline + measured truth are always added automatically;
  you do not need to list them.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _runner import (                                                # noqa: E402
    CAR_DIMS, baseline_v0, discover_segments, load_preset, load_segment,
    measured_truth, pick_segment, resolve_agent, run_agent, save_preset,
)


def _cmd_list(args: argparse.Namespace) -> None:
    segments = discover_segments()
    if args.platform:
        segments = [s for s in segments if s.platform == args.platform]
    print(f"{'idx':>4}  {'platform':32s}  device / route / segment")
    for i, s in enumerate(segments):
        print(f"  {i:3d}   {s.platform:32s}  "
              f"{s.device[:12]} / {s.route[:14]} / {s.idx}")
    if not segments:
        print("(no segments matched)")


def _cmd_compare(args: argparse.Namespace) -> None:
    segments = discover_segments()
    if not segments:
        raise SystemExit("No segments found under data/sim/segments/")

    # Merge preset + CLI args.
    preset = load_preset(args.preset) if args.preset else {}
    agent_specs: list[str] = list(preset.get("agents", []))
    agent_specs.extend(args.agent or [])

    segment_spec = args.segment if args.segment is not None else preset.get("segment")
    if segment_spec is None:
        raise SystemExit("Missing segment: pass one positionally or include it in the preset.")
    if isinstance(segment_spec, str) and segment_spec.isdigit():
        segment_spec = int(segment_spec)
    seg = pick_segment(segments, segment_spec)

    if args.save_preset:
        path = save_preset(args.save_preset, agent_specs, seg.slug if args.segment is not None else None)
        print(f"saved preset → {path}")
        if not (args.html or args.rrd or args.spawn):
            return  # save-only mode

    if not agent_specs:
        raise SystemExit("No agents specified. Pass --agent or --preset.")

    print(f"segment:  [{segments.index(seg)}] {seg.label}")
    df, schema = load_segment(seg)

    # Always include measured truth (if available) and V0 baseline first.
    track = CAR_DIMS[seg.platform]["track"]
    runs = []
    if schema.yaw_real_col is not None or schema.has_wheel_speeds:
        runs.append(measured_truth(df, schema, track))
    runs.append(baseline_v0(df, schema))

    for i, spec in enumerate(agent_specs):
        agent = resolve_agent(spec, default_color_idx=i)
        try:
            runs.append(run_agent(agent, df, seg.platform))
            print(f"  ✓ {agent.name}")
        except Exception as e:
            print(f"  ✗ {agent.name} → {type(e).__name__}: {e}")

    # Default backend: plotly HTML (unless --rrd/--spawn passed alone).
    do_html = args.html or (not args.rrd and not args.spawn)

    if do_html:
        from compare_plotly import render as render_html
        out = render_html(seg, df, schema, runs)
        print(f"wrote {out}")

    if args.rrd or args.spawn:
        from compare_rerun import render as render_rerun
        out = render_rerun(seg, df, schema, runs, spawn=args.spawn)
        if out is not None:
            print(f"wrote {out}")
            print(f"open with:  rerun {out}")


def main() -> None:
    # Special-case `list` before argparse to avoid a subparser/positional clash.
    if len(sys.argv) >= 2 and sys.argv[1] == "list":
        lp = argparse.ArgumentParser(prog="compare.py list")
        lp.add_argument("--platform", default=None)
        _cmd_list(lp.parse_args(sys.argv[2:]))
        return

    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("segment", nargs="?", default=None,
                   help="segment index (from `compare.py list`) or slug substring")
    p.add_argument("--agent", action="append", default=None,
                   help="agent path (relative to webinar-AI/); repeat for many. "
                        "Append :label to override the legend name.")
    p.add_argument("--preset", default=None, help="preset name (under presets/) or path")
    p.add_argument("--save-preset", default=None,
                   help="save the current --agent list (and segment) as a named preset")
    p.add_argument("--html", action="store_true", help="render plotly HTML (default)")
    p.add_argument("--rrd", action="store_true", help="save rerun .rrd")
    p.add_argument("--spawn", action="store_true", help="open rerun viewer live")

    args = p.parse_args()
    _cmd_compare(args)


if __name__ == "__main__":
    main()
