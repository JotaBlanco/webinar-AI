"""Cohort visualisations — plotly figures, exported as either:
  - interactive HTML <div> for embedding in cohort.html (uses CDN plotly.js)
  - static SVG string for embedding in print/PDF HTML (no JS dependency)

The same Figure object is reused for both formats so the two views are always
consistent.
"""

from __future__ import annotations

import json
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots


# Quix brand-ish palette for module families.
FAMILY_COLOURS = {
    "module-1": "#3366ff",   # blue
    "module-2": "#9966ff",   # purple
    "module-3": "#ff6600",   # orange
    "module-4": "#00cc99",   # green
    "raw":      "#888888",
    "unknown":  "#cccccc",
}

# Marker shapes per family — secondary encoding so the report is colourblind-survivable.
FAMILY_SHAPES = {
    "module-1": "circle",
    "module-2": "square",
    "module-3": "diamond",
    "module-4": "triangle-up",
    "raw":      "x",
    "unknown":  "cross",
}


def _family_colour(fam: str) -> str:
    return FAMILY_COLOURS.get(fam, "#666666")


def _family_shape(fam: str) -> str:
    return FAMILY_SHAPES.get(fam, "circle")


def _common_layout(fig: go.Figure, title: str, *, height: int = 480) -> go.Figure:
    fig.update_layout(
        title={"text": title, "x": 0.04, "xanchor": "left", "font": {"size": 18, "color": "#0a0b24"}},
        font={"family": "Geist, system-ui, -apple-system, sans-serif", "size": 13, "color": "#222"},
        plot_bgcolor="#fafafa",
        paper_bgcolor="#ffffff",
        margin={"l": 60, "r": 30, "t": 60, "b": 60},
        height=height,
        legend={"bgcolor": "rgba(255,255,255,0.85)", "bordercolor": "#e5e5e5", "borderwidth": 1},
    )
    fig.update_xaxes(showgrid=True, gridcolor="#eaeaea", zeroline=True, zerolinecolor="#999", zerolinewidth=1)
    fig.update_yaxes(showgrid=True, gridcolor="#eaeaea", zeroline=True, zerolinecolor="#999", zerolinewidth=1)
    return fig


def scatter_yaw_vs_cte(cohort: dict) -> go.Figure:
    """Headline scatter: x = yaw Δ%, y = CTE Δ%, one point per agent, colour+shape by family.
    Diagonal y=x reference line, V0 origin marked."""
    fig = go.Figure()

    # Group points by family so each family gets its own legend entry.
    fam_buckets: dict[str, dict] = {}
    for row in cohort["per_agent"]:
        if row["status"] != "ok":
            continue
        if row["yaw_pct"] is None or row["cte_pct"] is None:
            continue
        fam = row["family"]
        b = fam_buckets.setdefault(fam, {"x": [], "y": [], "text": [], "ids": []})
        b["x"].append(row["yaw_pct"])
        b["y"].append(row["cte_pct"])
        b["ids"].append(row["agent_id"])
        b["text"].append(
            f"<b>{row['agent_id']}</b><br>"
            f"yaw Δ%: {row['yaw_pct']:+.1f}%<br>"
            f"CTE Δ%: {row['cte_pct']:+.1f}%<br>"
            f"yaw RMSE: {row['yaw_agent_rmse']:.5f} rad/s<br>"
            f"CTE RMSE: {row['cte_agent_m']:.2f} m"
        )

    # Diagonal y=x reference line — agents above it improved CTE more than yaw.
    all_vals = [v for b in fam_buckets.values() for v in (b["x"] + b["y"])]
    if all_vals:
        lo = min(min(all_vals), 0) - 5
        hi = max(all_vals) + 5
        fig.add_trace(go.Scatter(
            x=[lo, hi], y=[lo, hi], mode="lines",
            line={"color": "#cccccc", "dash": "dot", "width": 1.5},
            name="y = x", hoverinfo="skip", showlegend=True,
        ))

    # Origin marker — V0 baseline at (0, 0).
    fig.add_trace(go.Scatter(
        x=[0], y=[0], mode="markers+text",
        marker={"symbol": "x", "color": "#999", "size": 12, "line": {"width": 2}},
        text=["V0"], textposition="bottom right", textfont={"color": "#666", "size": 11},
        name="V0 baseline", hoverinfo="text", hovertext="V0 baseline (origin)",
    ))

    for fam in sorted(fam_buckets.keys()):
        b = fam_buckets[fam]
        fig.add_trace(go.Scatter(
            x=b["x"], y=b["y"],
            mode="markers+text",
            marker={
                "symbol": _family_shape(fam), "color": _family_colour(fam),
                "size": 14, "line": {"color": "#fff", "width": 1.5},
                "opacity": 0.88,
            },
            text=[i.replace(f"m{fam[-1]}-", "") for i in b["ids"]] if fam.startswith("module-") else b["ids"],
            textposition="top center", textfont={"size": 10, "color": "#444"},
            name=fam, hovertext=b["text"], hoverinfo="text",
        ))

    _common_layout(fig, "Canonical performance — yaw vs CTE improvement (each agent = one point)", height=560)
    fig.update_xaxes(title_text="Yaw-rate RMSE Δ% vs V0  (higher = better instantaneous fidelity)")
    fig.update_yaxes(title_text="CTE RMSE Δ% vs V0  (higher = better cumulative trajectory)")
    return fig


def scatter_per_platform(cohort: dict) -> go.Figure:
    """Faceted scatter — one subplot per platform. Spots agents that excel on one platform only."""
    platforms = sorted(cohort.get("per_platform", {}).keys())
    if not platforms:
        return go.Figure()

    cols = len(platforms)
    fig = make_subplots(
        rows=1, cols=cols,
        subplot_titles=[p for p in platforms],
        horizontal_spacing=0.08,
    )

    # For each agent, pull per-platform yaw & CTE from its raw scorecard.
    # We've only got the cohort summary here — re-derive from per_platform via baseline.
    # Easiest: walk per_agent rows and the per_platform pivot together.
    # The cohort.json stores only the pivot summary; per-agent per-platform numbers
    # are on the per-agent scorecards. So we need to read them too — done by the caller
    # who already has them. For now, fall back to plotting only the overall point per
    # family/agent and use platform colour from the pivot.

    # Actually we DO have the data — embedded in per_agent rows under platforms_supported.
    # But not the per-platform improvement %s. To keep this self-contained without
    # re-reading per-agent files, we expose a precomputed `per_agent_per_platform`
    # list in cohort.json. For iter 2 first cut, plot the per_platform pivot as bars.
    # If you want per-agent dots per platform, that's iter 2.5.

    bl_yaw = cohort["baseline"]["yaw_rate"]["rmse_rad_per_s"]
    bl_cte = cohort["baseline"]["cte"]["rmse_meters"]

    # Pull from per-agent JSONs is not possible here. Use the per_agent_platform_breakdown
    # if cohort.json exposes it. Else show a bar comparison per platform.

    for col_idx, plat in enumerate(platforms, start=1):
        # Walk per_agent_platform if present
        ppb = cohort.get("per_agent_platform_breakdown") or {}
        fam_buckets: dict[str, dict] = {}
        for row in cohort["per_agent"]:
            if row["status"] != "ok":
                continue
            agent_plat = ppb.get(row["agent_id"], {}).get(plat)
            if not agent_plat:
                continue
            yp = agent_plat.get("yaw_improvement_pct")
            cp = agent_plat.get("cte_improvement_pct")
            if yp is None or cp is None:
                continue
            fam = row["family"]
            b = fam_buckets.setdefault(fam, {"x": [], "y": [], "text": [], "ids": []})
            b["x"].append(yp)
            b["y"].append(cp)
            b["ids"].append(row["agent_id"])
            b["text"].append(
                f"<b>{row['agent_id']}</b> on {plat}<br>"
                f"yaw Δ%: {yp:+.1f}%<br>"
                f"CTE Δ%: {cp:+.1f}%"
            )

        for fam in sorted(fam_buckets.keys()):
            b = fam_buckets[fam]
            fig.add_trace(go.Scatter(
                x=b["x"], y=b["y"], mode="markers",
                marker={
                    "symbol": _family_shape(fam), "color": _family_colour(fam),
                    "size": 11, "line": {"color": "#fff", "width": 1},
                    "opacity": 0.85,
                },
                name=fam, legendgroup=fam, showlegend=(col_idx == 1),
                hovertext=b["text"], hoverinfo="text",
            ), row=1, col=col_idx)

        fig.update_xaxes(title_text="yaw Δ%", row=1, col=col_idx, gridcolor="#eaeaea")
        fig.update_yaxes(title_text="CTE Δ%" if col_idx == 1 else "", row=1, col=col_idx, gridcolor="#eaeaea")

    _common_layout(fig, "Per-platform performance (each subplot = one platform)", height=420)
    return fig


def boxplot_per_segment(cohort: dict) -> go.Figure:
    """One box per agent — distribution of per-segment yaw RMSE. Reveals long-tail offenders."""
    fig = go.Figure()
    ps = cohort.get("per_segment", {})
    if not ps:
        return fig

    # Sort agents by family, then by median (best within family on the left).
    families = {r["agent_id"]: r["family"] for r in cohort["per_agent"]}
    agent_ids = sorted(
        [aid for aid in ps if ps[aid]["yaw_segment_rmse"]["n"] > 0],
        key=lambda a: (families.get(a, "z"), ps[a]["yaw_segment_rmse"].get("median") or 9999),
    )

    for aid in agent_ids:
        vals = ps[aid].get("yaw_segment_values", [])
        if not vals:
            continue
        fam = families.get(aid, "unknown")
        fig.add_trace(go.Box(
            y=vals, name=aid, boxmean="sd",
            marker={"color": _family_colour(fam)},
            line={"color": _family_colour(fam)},
            fillcolor=_family_colour(fam),
            opacity=0.65,
            boxpoints="suspectedoutliers",
            jitter=0.3,
        ))

    _common_layout(fig, "Per-segment yaw RMSE distribution (each box = one agent's per-segment spread)", height=520)
    fig.update_yaxes(title_text="yaw RMSE (rad/s)  — log axis", type="log", gridcolor="#eaeaea")
    fig.update_xaxes(tickangle=-45, gridcolor="#eaeaea")
    fig.update_layout(showlegend=False)
    return fig


def bars_per_family(cohort: dict) -> go.Figure:
    """Grouped bars: yaw Δ% and CTE Δ% per family (mean), with σ as error bars."""
    fig = go.Figure()
    families = cohort.get("family_order", [])
    if not families:
        return fig

    yaw_means = [cohort["families"][f]["yaw_pct"]["mean"] or 0 for f in families]
    yaw_std   = [cohort["families"][f]["yaw_pct"]["std"] or 0 for f in families]
    cte_means = [cohort["families"][f]["cte_pct"]["mean"] or 0 for f in families]
    cte_std   = [cohort["families"][f]["cte_pct"]["std"] or 0 for f in families]

    fig.add_trace(go.Bar(
        x=families, y=yaw_means, name="yaw Δ% (mean)",
        error_y={"type": "data", "array": yaw_std, "color": "#3366ff"},
        marker={"color": "#3366ff", "opacity": 0.85},
        hovertemplate="%{x}<br>yaw mean: %{y:+.1f}%<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=families, y=cte_means, name="CTE Δ% (mean)",
        error_y={"type": "data", "array": cte_std, "color": "#ff6600"},
        marker={"color": "#ff6600", "opacity": 0.85},
        hovertemplate="%{x}<br>CTE mean: %{y:+.1f}%<extra></extra>",
    ))

    _common_layout(fig, "Module-level performance (mean Δ% vs V0, ±σ as error bars)", height=420)
    fig.update_yaxes(title_text="improvement % vs V0", gridcolor="#eaeaea")
    fig.update_xaxes(title_text="")
    fig.update_layout(barmode="group", legend={"orientation": "h", "y": 1.12, "x": 0.5, "xanchor": "center"})
    return fig


def calibration_scatter(cohort: dict, *, kpi: str = "yaw") -> go.Figure:
    """Self-reported vs canonical Δ% for one KPI. y = x = perfect calibration.
    Above the line = overclaim; below = underclaim. Only populated when
    --with-self-reported was used.

    kpi: 'yaw' or 'cte'
    """
    fig = go.Figure()
    if not cohort.get("self_reported_loaded"):
        return fig

    claim_key = "claimed_yaw_pct" if kpi == "yaw" else "claimed_cte_pct"
    canon_key = "yaw_pct" if kpi == "yaw" else "cte_pct"
    label = "yaw" if kpi == "yaw" else "CTE"

    fam_buckets: dict[str, dict] = {}
    for row in cohort["per_agent"]:
        if row["status"] != "ok":
            continue
        claimed = row.get(claim_key)
        canon = row.get(canon_key)
        if claimed is None or canon is None:
            continue
        fam = row["family"]
        b = fam_buckets.setdefault(fam, {"x": [], "y": [], "text": [], "ids": []})
        b["x"].append(claimed)
        b["y"].append(canon)
        b["ids"].append(row["agent_id"])
        gap = claimed - canon
        b["text"].append(
            f"<b>{row['agent_id']}</b><br>"
            f"claimed {label}: {claimed:+.1f}%<br>"
            f"canonical {label}: {canon:+.1f}%<br>"
            f"gap (claim − canonical): {gap:+.1f} pp"
        )

    # y = x reference line — perfect calibration.
    all_vals = [v for b in fam_buckets.values() for v in (b["x"] + b["y"])]
    if all_vals:
        lo = min(min(all_vals), 0) - 5
        hi = max(all_vals) + 5
        fig.add_trace(go.Scatter(
            x=[lo, hi], y=[lo, hi], mode="lines",
            line={"color": "#cccccc", "dash": "dash", "width": 1.5},
            name="perfect calibration (y=x)", hoverinfo="skip",
        ))

    for fam in sorted(fam_buckets.keys()):
        b = fam_buckets[fam]
        fig.add_trace(go.Scatter(
            x=b["x"], y=b["y"], mode="markers+text",
            marker={"symbol": _family_shape(fam), "color": _family_colour(fam),
                    "size": 13, "line": {"color": "#fff", "width": 1.5}, "opacity": 0.88},
            text=[i.replace(f"m{fam[-1]}-", "") for i in b["ids"]] if fam.startswith("module-") else b["ids"],
            textposition="top center", textfont={"size": 10, "color": "#444"},
            name=fam, hovertext=b["text"], hoverinfo="text",
        ))

    _common_layout(fig, f"Self-awareness diagnostic — claimed vs canonical {label} Δ%", height=480)
    fig.update_xaxes(title_text=f"Claimed {label} Δ% (what the agent said in their REPORT)")
    fig.update_yaxes(title_text=f"Canonical {label} Δ% (measured on held-out pool)")
    return fig


# --- Export helpers ----------------------------------------------------------

def to_interactive_html(fig: go.Figure, *, div_id: str) -> str:
    """Return an <div> that, with plotly.js loaded, renders interactively."""
    return fig.to_html(
        include_plotlyjs=False,  # outer template links plotly CDN once
        full_html=False,
        div_id=div_id,
        config={"displaylogo": False, "modeBarButtonsToRemove": ["sendDataToCloud"]},
    )


def to_static_svg(fig: go.Figure, *, width: int = 1000, height: int | None = None) -> str:
    """Return an inline <svg>...</svg> string for embedding in PDF-bound HTML."""
    h = height or fig.layout.height or 500
    svg_bytes = fig.to_image(format="svg", width=width, height=h, scale=1)
    return svg_bytes.decode("utf-8")
