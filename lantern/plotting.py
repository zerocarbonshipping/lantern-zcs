# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

import logging
import math
import os
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config
from .percentiles import (
    darken_hex,
    get_color,
    hex_to_rgba,
    label_matches_scenario,
    main_scenario_for_label,
    metric_columns,
    quantiles_np,
)
from .timesteps import align_and_interpolate_to_quarters

logger = logging.getLogger(__name__)


def _scenario_title(scenario: str) -> str:
    return config.SCENARIO_TITLES.get(scenario, scenario)


def _cfg() -> config.RootConfig:
    return config._LAST_CONFIG or config.RootConfig()


def _html_legend() -> dict:
    P = config.PLOTS
    return dict(
        orientation=P.legend_orientation,
        x=P.legend_x,
        y=P.legend_y,
        xanchor=P.legend_xanchor,
        yanchor=P.legend_yanchor,
    )


def _apply_html_style(fig: go.Figure, *, title: str, xaxis_title: str, yaxis_title: str, height: int | None = None):
    P = config.PLOTS
    fig.update_yaxes(rangemode=P.y_rangemode)
    fig.update_layout(
        title=title,
        xaxis_title=xaxis_title,
        yaxis_title=yaxis_title,
        paper_bgcolor=P.paper_bgcolor,
        plot_bgcolor=P.plot_bgcolor,
        showlegend=P.show_legend,
        legend=_html_legend(),
        margin=dict(t=P.margin_top, r=P.margin_right, b=P.margin_bottom, l=P.margin_left),
        **({"autosize": True, "height": height} if height is not None else {}),
    )


def _line_style(color: str, width: float, dash_override: str | None, fallback_dash: str | None = None) -> dict:
    line = dict(color=color, width=width)
    dash = dash_override if dash_override is not None else fallback_dash
    if dash:
        line["dash"] = dash
    return line


def _band_fill(color: str) -> str:
    return hex_to_rgba(color, _cfg().quantiles.band_alpha)


def _median_line(color: str, fallback_dash: str | None = None) -> dict:
    q = _cfg().quantiles
    return _line_style(color, q.median_line_width, q.median_dash, fallback_dash)


def _representative_line(color: str, fallback_dash: str | None = None, *,
                         width_override: float | None = None, dash_override: str | None = None) -> dict:
    r = _cfg().representatives
    width = width_override if width_override is not None else r.line_width
    dash = dash_override if dash_override is not None else r.dash
    return _line_style(color, width, dash, fallback_dash)


def _representative_color(color: str) -> str:
    return darken_hex(color, _cfg().representatives.darken_factor)


def _apply_ppt_style(fig: go.Figure, metric_hdr: str):
    P = config.PPT
    # Title
    if P.title_show:
        auto_title = metric_hdr
        title_text = f"{P.title_prefix}{auto_title}{P.title_suffix}"
    else:
        title_text = None

    fig.update_layout(
        title=dict(text=title_text, font=dict(size=P.title_size)) if title_text else None,
        font=dict(family=P.font_family, size=P.base_font_size),
        paper_bgcolor="rgba(0,0,0,0)" if P.transparent else "white",
        plot_bgcolor="rgba(0,0,0,0)" if P.transparent else "white",
        margin=dict(t=P.margin_top, r=P.margin_right, b=P.margin_bottom, l=P.margin_left),
        showlegend=P.legend_show,
        legend=dict(
            orientation=P.legend_orientation,
            x=P.legend_x, y=P.legend_y,
            xanchor=P.legend_xanchor, yanchor=P.legend_yanchor
        ),
    )

    # X axis
    fig.update_xaxes(
        title_text=P.x_title_text if P.x_title_show else None,
        showline=P.x_show_line, linewidth=P.axis_linewidth, linecolor="rgba(0,0,0,0.8)",
        ticks="outside" if P.x_show_ticks else "",
        showticklabels=P.x_show_ticklabels,
        showgrid=P.x_show_grid, zeroline=False,
        tickangle=P.x_tick_angle
    )

    # Y axis
    fig.update_yaxes(
        title_text=metric_hdr if P.y_title_show else None,
        showline=P.y_show_line, linewidth=P.axis_linewidth, linecolor="rgba(0,0,0,0.8)",
        ticks="outside" if P.y_show_ticks else "",
        showticklabels=P.y_show_ticklabels,
        showgrid=P.y_show_grid, zeroline=False,
        rangemode="tozero"
    )


def _rgba_with_alpha(color: str, alpha: float) -> str:
    color = (color or "").strip()
    if color.startswith("#") and len(color) in (4, 7):
        return hex_to_rgba(color, alpha)
    if color.lower().startswith("rgba"):
        try:
            inside = color[color.find("(") + 1:color.rfind(")")]
            r, g, b, _ = [x.strip() for x in inside.split(",")]
            return f"rgba({r},{g},{b},{alpha})"
        except Exception:
            return color
    return color


def _build_ppt_figure_from(fig_html: go.Figure, metric_hdr: str) -> go.Figure:
    """Create a new PPT-styled figure using roles (meta.role); fallback heuristics if missing."""
    P = config.PPT
    fig_ppt = go.Figure()

    def infer_role(tr: go.Scatter) -> str | None:
        meta = getattr(tr, "meta", None)
        if isinstance(meta, dict) and "role" in meta:
            return meta["role"]
        # Heuristics fallback:
        name = (getattr(tr, "name", "") or "").lower()
        if getattr(tr, "fill", None) == "tonexty":
            return "band_upper"
        lw = getattr(getattr(tr, "line", None), "width", None)
        if lw == 0:
            return "band_lower"
        if "median" in name:
            return "median"
        if "representative" in name:
            return "rep"
        return None

    for tr in fig_html.data:
        if not isinstance(tr, go.Scatter):
            continue

        role = infer_role(tr)

        kwargs = dict(
            x=getattr(tr, "x", None),
            y=getattr(tr, "y", None),
            mode=getattr(tr, "mode", "lines"),
            name=getattr(tr, "name", None),
            legendgroup=getattr(tr, "legendgroup", None),
            showlegend=getattr(tr, "showlegend", False),
            hoverinfo=getattr(tr, "hoverinfo", None),
        )

        if role == "faint":
            # Preserve the look of “traces” mode in PPT output
            lc = getattr(tr, "line", None)
            color = getattr(lc, "color", None) if lc else None
            dash = getattr(lc, "dash", None) if lc else None
            width = getattr(lc, "width", None)

            kwargs["line"] = dict(
                color=color,
                width=(width if width is not None else config.TRACES_LINE_WIDTH),
                dash=dash,
            )
            kwargs["opacity"] = getattr(tr, "opacity", config.TRACES_OPACITY)

            fig_ppt.add_trace(go.Scatter(**kwargs))
            continue

        if role in ("band_lower", "band_upper"):
            if role == "band_lower":
                kwargs["line"] = dict(width=0)
            else:
                kwargs["line"] = dict(width=0)
                kwargs["fill"] = "tonexty"
                fc = getattr(tr, "fillcolor", None)
                kwargs["fillcolor"] = _rgba_with_alpha(fc, P.band_alpha) if fc else fc

        elif role == "median":
            lc = getattr(tr, "line", None)
            color = getattr(lc, "color", None) if lc else None
            kwargs["line"] = dict(color=color, width=P.median_line_width)

        elif role == "rep":
            lc = getattr(tr, "line", None)
            color = getattr(lc, "color", None) if lc else None
            # Use per-target styling from the trace's original line if available
            orig_width = getattr(lc, "width", None) if lc else None
            orig_dash = getattr(lc, "dash", None) if lc else None
            kwargs["line"] = dict(
                color=color,
                width=orig_width if orig_width is not None else P.representative_width,
                dash=orig_dash if orig_dash is not None else P.representative_dash,
            )

        else:
            # Unknown/other: preserve line properties to avoid losing traces
            lc = getattr(tr, "line", None)
            if lc:
                kwargs["line"] = dict(color=getattr(lc, "color", None), width=getattr(lc, "width", 1))

        fig_ppt.add_trace(go.Scatter(**kwargs))

    _apply_ppt_style(fig_ppt, metric_hdr)
    return fig_ppt


def _export_png(fig: go.Figure, out_path: Path):
    """Export high-res PNG using kaleido."""
    w, h, s = config.PPT.width_px, config.PPT.height_px, config.PPT.scale
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Suppress verbose stdout/stderr from kaleido/choreographer/Chromium
        devnull = os.open(os.devnull, os.O_WRONLY)
        old_stdout, old_stderr = os.dup(1), os.dup(2)
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        try:
            fig.write_image(
                str(out_path),
                format="png",
                width=w, height=h,
                scale=s, engine="kaleido"
            )
        finally:
            os.dup2(old_stdout, 1)
            os.dup2(old_stderr, 2)
            os.close(old_stdout)
            os.close(old_stderr)
            os.close(devnull)
        logger.debug(f"Saved PPT PNG: {out_path}")
    except Exception as e:
        logger.exception(f"PPT export failed for {out_path}: {e}")


def add_faint_traces(fig, xvals, data_block, col_indices, label_lookup, row=None, col=None, legend_seen=None):
    """
    Draw raw traces. label_lookup(j) should return a string that includes the scenario
    name (so get_color can derive a color), ideally the full sample label for a clear legend.
    If row/col are provided, traces are added to that subplot cell.

    If legend_seen is a set, it will be used to deduplicate legend entries across the
    whole figure (show each trace name at most once).
    """
    if config.MAX_TRACES_PER_SUBPLOT <= 0:
        return
    n = len(col_indices)
    if n == 0:
        return

    # downsample if too many
    if n > config.MAX_TRACES_PER_SUBPLOT:
        step = max(1, n // config.MAX_TRACES_PER_SUBPLOT)
        idxs = list(range(0, n, step))[:config.MAX_TRACES_PER_SUBPLOT]
    else:
        idxs = list(range(n))

    # dashing & styling from config
    use_dashing = getattr(config, "TRACES_PER_TRACE_DASHING", False)
    dash_cycle = getattr(config, "TRACES_DASH_CYCLE", ["solid", "dash", "dot", "longdash", "dashdot", "longdashdot"])
    show_all = getattr(config, "TRACES_COMPLETE_LEGEND", False)
    scenario_legend = getattr(config, "TRACES_SCENARIO_LEGEND", True)
    line_width = float(getattr(config, "TRACES_LINE_WIDTH", 1.0))
    opacity = float(getattr(config, "TRACES_OPACITY", 0.25))

    # Local dedup set when no external one is provided
    local_seen = set()
    seen = legend_seen if legend_seen is not None else local_seen

    # Pre-compute scenario counts for hover info (over displayed traces only)
    scenario_counts: dict = {}
    if scenario_legend and not show_all:
        for k_idx in idxs:
            j = col_indices[k_idx]
            sc = main_scenario_for_label(str(label_lookup(j)))
            scenario_counts[sc] = scenario_counts.get(sc, 0) + 1

    for k in idxs:
        j = col_indices[k]
        y = data_block[:, j]
        name_label = str(label_lookup(j))  # full sample label (includes scenario)
        color = get_color(name_label)
        dash = dash_cycle[k % len(dash_cycle)] if use_dashing and dash_cycle else None

        if show_all:
            # Legacy per-sample legend mode
            display_name = name_label
            showlegend = True
            legend_group = name_label
            if name_label in seen:
                showlegend = False
                display_name = None
            else:
                seen.add(name_label)
            hovertemplate = None
            hoverlabel = dict(namelength=-1)
        elif scenario_legend:
            # New per-scenario legend mode
            scenario = main_scenario_for_label(name_label)
            scenario_title = _scenario_title(scenario) if scenario else name_label
            legend_key = scenario or name_label
            showlegend = legend_key not in seen
            if showlegend:
                seen.add(legend_key)
            display_name = scenario_title
            legend_group = legend_key
            sc_count = scenario_counts.get(scenario, "?")
            hovertemplate = (
                f"<b>{scenario_title}</b><br>"
                f"Sample: {name_label}<br>"
                f"n={sc_count} traces<br>"
                f"x: %{{x}}<br>"
                f"y: %{{y:.2f}}"
                f"<extra></extra>"
            )
            hoverlabel = None
        else:
            # No legend at all
            display_name = None
            showlegend = False
            legend_group = None
            hovertemplate = None
            hoverlabel = dict(namelength=-1)

        kwargs = dict(
            x=xvals, y=y,
            mode="lines",
            name=display_name,
            showlegend=showlegend,
            legendgroup=legend_group,
            line=dict(color=color, width=line_width, dash=dash),
            opacity=opacity,
            meta=dict(role="faint"),
        )
        if hovertemplate:
            kwargs["hovertemplate"] = hovertemplate
        if hoverlabel:
            kwargs["hoverlabel"] = hoverlabel

        trace = go.Scatter(**kwargs)
        if row is not None and col is not None:
            fig.add_trace(trace, row=row, col=col)
        else:
            fig.add_trace(trace)


def plot_single_metric(df, dfv, years, rows_idx, metric_hdr, short, mode, reps, outdir, data_rows=None):
    cols_all = metric_columns(df, metric_hdr, scenario_key=None)
    if not cols_all:
        logger.warning(f"no columns for '{metric_hdr}'.")
        return False

    if data_rows is None:
        data_rows = dfv[rows_idx]

    # Combined view
    fig = go.Figure()
    data_block = data_rows[:, cols_all].astype(float, copy=False)
    xvals = years

    if mode == "traces":
        try:
            x_aligned, aligned = align_and_interpolate_to_quarters(df, dfv, rows_idx, cols_all)
            xvals = x_aligned
            data_block = aligned
        except Exception as e:
            logger.warning(f"Traces alignment failed for '{metric_hdr}' — falling back to yearly rows: {e}")

        label_lookup = lambda j: str(dfv[0, cols_all[j]])
        add_faint_traces(fig, xvals, data_block, list(range(len(cols_all))), label_lookup)

    if mode == "quantiles":
        q_lo = config.QUANTILES_Q_LOW
        q_hi = config.QUANTILES_Q_HIGH
        band_label = f"p{q_lo:g}–p{q_hi:g}"
        rep_targets = getattr(config, "REP_TARGETS", [])

        for scenario in config.SCENARIOS:
            scenario_positions = [k for k, c in enumerate(cols_all) if label_matches_scenario(dfv[0, c], scenario)]
            if not scenario_positions:
                continue
            block = data_block[:, scenario_positions]
            p5, p50, p95 = quantiles_np(block, q_low=q_lo, q_high=q_hi)
            if p5 is None:
                continue
            color = config.COLOR_MAP.get(scenario, "grey")
            scenario_title = _scenario_title(scenario)
            dark = _representative_color(color)

            fig.add_trace(go.Scatter(x=xvals, y=p5, mode="lines",
                                     name=f"{scenario_title} {band_label}", line=dict(width=0),
                                     showlegend=True, legendgroup=scenario, hoverinfo="skip", meta=dict(role="band_lower")))
            fig.add_trace(go.Scatter(x=xvals, y=p95, mode="lines",
                                     name=f"{scenario_title} {band_label}", line=dict(width=0),
                                     fill="tonexty", fillcolor=_band_fill(color),
                                     showlegend=False, legendgroup=scenario, hoverinfo="skip", meta=dict(role="band_upper")))
            if config.QUANTILES_SHOW_MEDIAN:
                fig.add_trace(go.Scatter(x=xvals, y=p50, mode="lines",
                                         name=f"{scenario_title} median", line=_median_line(color, fallback_dash="dash"),
                                         showlegend=True, legendgroup=scenario, meta=dict(role="median")))

            # Representative overlay(s)
            if getattr(config, "SHOW_REPRESENTATIVES", True):
                scenario_reps = reps.get(scenario, {})
                for target_cfg in rep_targets:
                    if not target_cfg.show:
                        continue
                    target_info = scenario_reps.get(target_cfg.percentile, {})
                    rep_label = target_info.get("sample_label")
                    if not rep_label:
                        continue
                    rep_pos = None
                    for idx_in_block, col_idx in enumerate([cols_all[p] for p in scenario_positions]):
                        if str(dfv[0, col_idx]) == rep_label:
                            rep_pos = idx_in_block
                            break
                    if rep_pos is not None:
                        y_rep = block[:, rep_pos]
                        rep_name = f"{scenario_title} {target_cfg.label}"
                        fig.add_trace(go.Scatter(
                            x=xvals, y=y_rep, mode="lines",
                            name=rep_name,
                            line=_representative_line(dark, width_override=target_cfg.line_width,
                                                      dash_override=target_cfg.dash),
                            showlegend=True, legendgroup=scenario,
                            meta=dict(role="rep", percentile=target_cfg.percentile)
                        ))

    if mode == "traces":
        fig.update_xaxes(tickformat=config.PLOTS.traces_tickformat)
    _apply_html_style(
        fig,
        title=f"{metric_hdr} (All)",
        xaxis_title=("Time" if mode == "traces" else "Year"),
        yaxis_title=metric_hdr,
    )
    out = outdir / f"{short}.html"
    fig.write_html(str(out), include_plotlyjs="cdn", full_html=True)
    logger.debug(f"Saved: {out}")

    if config.PPT.enabled:
        fig_ppt = _build_ppt_figure_from(fig, metric_hdr)
        png_dir = outdir / config.PPT.ppt_subdir
        _export_png(fig_ppt, png_dir / f"{short}{config.PPT.filename_suffix}.png")

    # Per-scenario
    for scenario in config.SCENARIOS:
        cols = metric_columns(df, metric_hdr, scenario_key=scenario)
        if not cols:
            continue
        fig = go.Figure()
        block = data_rows[:, cols].astype(float, copy=False)
        xvals = years

        if mode == "traces":
            try:
                x_aligned, aligned = align_and_interpolate_to_quarters(df, dfv, rows_idx, cols)
                xvals = x_aligned
                block = aligned
            except Exception as e:
                logger.warning(f"Traces alignment failed for '{metric_hdr}' ({scenario}) — fallback to yearly: {e}")

            label_lookup = lambda j: str(dfv[0, cols[j]])
            add_faint_traces(fig, xvals, block, list(range(len(cols))), label_lookup)

        if mode == "quantiles":
            q_lo = config.QUANTILES_Q_LOW
            q_hi = config.QUANTILES_Q_HIGH
            band_label = f"p{q_lo:g}–p{q_hi:g}"
            rep_targets = getattr(config, "REP_TARGETS", [])

            p5, p50, p95 = quantiles_np(block, q_low=q_lo, q_high=q_hi)
            if p5 is None:
                continue
            color = config.COLOR_MAP.get(scenario, "grey")
            scenario_title = _scenario_title(scenario)
            dark = _representative_color(color)

            fig.add_trace(go.Scatter(x=xvals, y=p5, mode="lines",
                                     name=f"{scenario_title} {band_label}", line=dict(width=0),
                                     showlegend=True, legendgroup=scenario, hoverinfo="skip", meta=dict(role="band_lower")))
            fig.add_trace(go.Scatter(x=xvals, y=p95, mode="lines",
                                     name=f"{scenario_title} {band_label}", line=dict(width=0),
                                     fill="tonexty", fillcolor=_band_fill(color),
                                     showlegend=False, legendgroup=scenario, hoverinfo="skip", meta=dict(role="band_upper")))
            if config.QUANTILES_SHOW_MEDIAN:
                fig.add_trace(go.Scatter(x=xvals, y=p50, mode="lines",
                                         name=f"{scenario_title} median",
                                         line=_median_line(color),
                                         showlegend=True, legendgroup=scenario, meta=dict(role="median")))

            if getattr(config, "SHOW_REPRESENTATIVES", True):
                scenario_reps = reps.get(scenario, {})
                for target_cfg in rep_targets:
                    if not target_cfg.show:
                        continue
                    target_info = scenario_reps.get(target_cfg.percentile, {})
                    rep_label = target_info.get("sample_label")
                    if not rep_label:
                        continue
                    rep_pos = None
                    for idx_in_block, col_idx in enumerate(cols):
                        if str(dfv[0, col_idx]) == rep_label:
                            rep_pos = idx_in_block
                            break
                    if rep_pos is not None:
                        y_rep = block[:, rep_pos]
                        rep_name = f"{scenario_title} {target_cfg.label}"
                        fig.add_trace(go.Scatter(
                            x=xvals, y=y_rep, mode="lines",
                            name=rep_name,
                            line=_representative_line(dark, fallback_dash="dash",
                                                      width_override=target_cfg.line_width,
                                                      dash_override=target_cfg.dash),
                            showlegend=True, legendgroup=scenario,
                            meta=dict(role="rep", percentile=target_cfg.percentile)
                        ))

        if mode == "traces":
            fig.update_xaxes(tickformat=config.PLOTS.traces_tickformat)
        _apply_html_style(
            fig,
            title=f"{metric_hdr} ({scenario.capitalize()})",
            xaxis_title=("Time" if mode == "traces" else "Year"),
            yaxis_title=metric_hdr,
        )
        subdir = outdir / scenario
        subdir.mkdir(exist_ok=True, parents=True)
        out = subdir / f"{short}.html"
        fig.write_html(str(out), include_plotlyjs="cdn", full_html=True)
        logger.debug(f"Saved: {out}")

        if config.PPT.enabled:
            fig_ppt = _build_ppt_figure_from(fig, metric_hdr)
            png_dir = subdir / config.PPT.ppt_subdir  # save under scenario/<ppt>
            _export_png(fig_ppt, png_dir / f"{short}{config.PPT.filename_suffix}.png")


def plot_multi_metric(df, dfv, years, rows_idx, metric_hdr, short, grid_cols, mode, reps, outdir, data_rows=None):
    cols_all = metric_columns(df, metric_hdr, scenario_key=None)
    if not cols_all:
        logger.warning(f"no columns for '{metric_hdr}'.")
        return False
    if data_rows is None:
        data_rows = dfv[rows_idx]
    sub_labels_all = dfv[config.SUBCAT_ROW, cols_all].astype(str).tolist()

    def render_view(scenario_key):
        # Track legend entries we've already shown (for traces mode)
        legend_seen = set()

        if scenario_key:
            sel_cols = [c for c in cols_all if label_matches_scenario(dfv[0, c], scenario_key)]
            scenarios_to_plot = [scenario_key]
        else:
            sel_cols = list(cols_all)
            scenarios_to_plot = config.SCENARIOS
        if not sel_cols:
            return None

        labels_for_sel = [sub_labels_all[cols_all.index(c)] for c in sel_cols]
        if short in config.SKIP_SUB:
            filtered = [(lab, c) for lab, c in zip(labels_for_sel, sel_cols) if lab not in config.SKIP_SUB[short]]
            if not filtered:
                return None
            labels_for_sel, sel_cols = zip(*filtered)
            labels_for_sel = list(labels_for_sel)
            sel_cols = list(sel_cols)

        unique_sublabs = []
        for lab in labels_for_sel:
            if lab not in unique_sublabs:
                unique_sublabs.append(lab)

        nrows = int(math.ceil(len(unique_sublabs) / float(grid_cols)))
        data_block = data_rows[:, sel_cols].astype(float, copy=False)
        x_vals = years
        if mode == "traces":
            try:
                x_aligned, aligned = align_and_interpolate_to_quarters(df, dfv, rows_idx, sel_cols)
                x_vals = x_aligned
                data_block = aligned
            except Exception as e:
                logger.warning(
                    f"Traces alignment failed for '{metric_hdr}' (scenario={scenario_key or 'ALL'}) — fallback to yearly: {e}")

        gmax = np.nanmax(data_block) if data_block.size else None

        fig = make_subplots(
            rows=nrows, cols=grid_cols,
            subplot_titles=unique_sublabs,
            shared_xaxes=True, shared_yaxes=True,
            vertical_spacing=0.08, horizontal_spacing=0.05
        )

        sublab_to_positions = {u: [] for u in unique_sublabs}
        for pos, _c in enumerate(sel_cols):
            sublab_to_positions[labels_for_sel[pos]].append(pos)

        legend_shown = set()
        for idx, sublab in enumerate(unique_sublabs):
            row = idx // grid_cols + 1
            col = idx % grid_cols + 1
            pos_list = sublab_to_positions[sublab]
            if not pos_list:
                continue

            if mode == "traces":
                # p is index *within this panel* (pos_list). Map back to the original column index.
                def label_lookup(p):
                    return str(dfv[0, sel_cols[pos_list[p]]])

                # Draw only this panel’s traces *in this cell*
                add_faint_traces(
                    fig,
                    x_vals,
                    data_block[:, pos_list],
                    list(range(len(pos_list))),
                    label_lookup,
                    row=row,
                    col=col,
                    legend_seen=legend_seen,
                )

                # Keep fixed Y like quantiles view
                if gmax is not None and np.isfinite(gmax):
                    fig.update_yaxes(range=[0, gmax], row=row, col=col)
                fig.update_yaxes(rangemode=config.PLOTS.y_rangemode, row=row, col=col)
                fig.update_xaxes(showticklabels=True, tickformat=config.PLOTS.traces_tickformat, row=row, col=col)
                continue  # skip quantile bands/median/rep for traces mode

            q_lo = config.QUANTILES_Q_LOW
            q_hi = config.QUANTILES_Q_HIGH
            band_label = f"p{q_lo:g}–p{q_hi:g}"
            rep_targets = getattr(config, "REP_TARGETS", [])

            for plot_scenario in scenarios_to_plot:
                scenario_positions = [p for p in pos_list if label_matches_scenario(dfv[0, sel_cols[p]], plot_scenario)]
                if not scenario_positions:
                    continue
                block = data_block[:, scenario_positions]
                p5, p50, p95 = quantiles_np(block, q_low=q_lo, q_high=q_hi)
                if p5 is None:
                    continue
                color = config.COLOR_MAP.get(plot_scenario, "grey")
                dark = _representative_color(color)

                scenario_title = _scenario_title(plot_scenario)
                show_leg = plot_scenario not in legend_shown
                name_prefix = scenario_title if show_leg else f"{sublab} {scenario_title}"
                legend_group = plot_scenario

                fig.add_trace(go.Scatter(x=x_vals, y=p5, mode="lines",
                                         name=f"{name_prefix} {band_label}", line=dict(width=0),
                                         showlegend=show_leg, legendgroup=legend_group, hoverinfo="skip"),
                              row=row, col=col)
                fig.add_trace(go.Scatter(x=x_vals, y=p95, mode="lines",
                                         name=f"{name_prefix} {band_label}", line=dict(width=0),
                                         fill="tonexty", fillcolor=_band_fill(color),
                                         showlegend=False, legendgroup=legend_group, hoverinfo="skip"),
                              row=row, col=col)
                if config.QUANTILES_SHOW_MEDIAN:
                    fig.add_trace(go.Scatter(x=x_vals, y=p50, mode="lines",
                                             name=f"{name_prefix} median",
                                             line=_median_line(color, fallback_dash="dash"),
                                             showlegend=show_leg, legendgroup=legend_group),
                                  row=row, col=col)
                if getattr(config, "SHOW_REPRESENTATIVES", True):
                    scenario_reps = reps.get(plot_scenario, {})
                    for target_cfg in rep_targets:
                        if not target_cfg.show:
                            continue
                        target_info = scenario_reps.get(target_cfg.percentile, {})
                        rep_label = target_info.get("sample_label")
                        if not rep_label:
                            continue
                        rep_pos = None
                        for idx_in_block, p in enumerate(scenario_positions):
                            col_idx = sel_cols[p]
                            if str(dfv[0, col_idx]) == rep_label:
                                rep_pos = idx_in_block
                                break
                        if rep_pos is not None:
                            y_rep = block[:, rep_pos]
                            fig.add_trace(go.Scatter(
                                x=x_vals, y=y_rep, mode="lines",
                                name=f"{name_prefix} {target_cfg.label}",
                                line=_representative_line(dark,
                                                          width_override=target_cfg.line_width,
                                                          dash_override=target_cfg.dash),
                                showlegend=show_leg, legendgroup=legend_group
                            ), row=row, col=col)

                if show_leg:
                    legend_shown.add(plot_scenario)

            if gmax is not None and np.isfinite(gmax):
                fig.update_yaxes(range=[0, gmax], row=row, col=col)
            fig.update_yaxes(rangemode=config.PLOTS.y_rangemode, row=row, col=col)
            fig.update_xaxes(
                showticklabels=True,
                tickformat=(config.PLOTS.traces_tickformat if mode == "traces" else None),
                row=row, col=col
            )

        height = config.FIXED_HEIGHT if nrows <= 3 else config.MIN_ROW_HEIGHT * nrows
        title = (f"{metric_hdr} [fixed Y]" if scenario_key is None
                 else f"{metric_hdr} ({_scenario_title(scenario_key)}) [fixed Y]")
        _apply_html_style(
            fig,
            title=title,
            xaxis_title="",
            yaxis_title="",
            height=height,
        )
        return fig

    # Combined view
    fig = render_view(None)
    if fig:
        out = outdir / f"{short}_grid.html"
        fig.write_html(str(out), include_plotlyjs="cdn", full_html=True)
        logger.debug(f"Saved: {out}")

    # Per-scenario
    for scenario in config.SCENARIOS:
        fig = render_view(scenario)
        if fig:
            subdir = outdir / scenario
            subdir.mkdir(exist_ok=True, parents=True)
            out = subdir / f"{short}_grid.html"
            fig.write_html(str(out), include_plotlyjs="cdn", full_html=True)
            logger.debug(f"Saved: {out}")
