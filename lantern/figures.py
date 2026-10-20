# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Draw the prepared series of one or more runs as a Plotly figure, one panel per value of the plot's panels.

An ensemble's lines and areas are its median with a band between the percentiles of its samples and a dotted line of
its representative sample; stacks show the representative sample, as medians and percentiles do not add up. Several
runs share the panels in a colour each where colour tells nothing else, that is where no panel's layer has more than
one label; stacks and the other plots get a column of panels per run.
"""

from __future__ import annotations

import itertools
import math
import re
from collections.abc import Callable

import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots

from lantern.config import Config, Plot
from lantern.data import BAND

# unit head to (base unit, power of ten of the head); counts and money keep their unit, plotly's ticks scale them
_SCALABLE = {"GJ": ("J", 9), "MJ": ("J", 6), "J": ("J", 0), "t": ("t", 0), "tCO2e": ("tCO2e", 0), "MW": ("W", 6), "W": ("W", 0)}
_PREFIXES = {3: "k", 6: "M", 9: "G", 12: "T", 15: "P", 18: "E"}
_PANEL_HEIGHT = 280  # px, per row of panels; the page grows a figure to fill the window
_LINE_WIDTH = 2.0


def build(
    plot: Plot, series: pl.DataFrame, unit: str, config: Config, runs: dict[str, str], panel: str | None = None,
) -> go.Figure:
    """Draw one plot of the runs, named in order in runs, or only the given panel, enlarged."""
    rank = _rank(config)
    present = set(series.get_column("run").unique().to_list())
    runs = {run: name for run, name in runs.items() if run in present}
    panels = sorted(series.get_column("panel").unique().to_list(), key=rank)
    labels = sorted(series.get_column("label").unique().to_list())
    style = config.style
    overlay = len(runs) > 1 and _overlays(plot, series)
    tiled = len(runs) > 1 and not overlay
    # overlaid, a panel of one label needs only the runs told apart, in the legend too
    by_run = overlay and _most_labels(series, "panel") <= 1

    if overlay:
        colors = dict(zip(runs, itertools.cycle(style.palette)))

    else:
        free = itertools.cycle(style.palette)
        colors = {label: style.colors.get(label) or next(free) for label in labels}

    # every panel, [value, title], for the page to enlarge one; an enlarged panel keeps the colours
    meta = [[p, config.labels.get(p, p)] for p in panels]

    if panel in panels:
        series, panels = series.filter(pl.col("panel") == panel), [panel]

    divisor, unit = scale_unit(series.select(pl.col("value").abs().max()).item() or 0.0, unit)
    series = series.with_columns(pl.col("low", "value", "high", "representative") / divisor)

    # a cell per panel, or tiled per panel and run: a row per panel and a column per run, sharing the y axis
    columns = list(runs) if tiled else [None]
    cells = [(p, run) for p in panels for run in columns]
    rows, cols = (len(panels), len(columns)) if tiled and len(panels) > 1 else _shape(len(cells))
    titles = [" · ".join(filter(None, (config.labels.get(p, p), runs.get(run)))) for p, run in cells]
    figure = _grid(titles, rows, cols, ("rows" if len(panels) > 1 else "all") if tiled else False)
    # the page's panel select lists the panels, and a click on a cell enlarges its panel
    figure.update_layout(meta={"panels": meta, "cells": [p for p, _ in cells]})
    shown = set()

    # traces go in panel, run, layer and label order, which sets the stacking and the legend
    groups = series.partition_by("panel", "run", "layer", "label", as_dict=True)
    order = sorted(groups, key=lambda k: (panels.index(k[0]), list(runs).index(k[1]), k[2], rank(k[3])))

    for panel, run, layer_index, label in order:
        line, layer = groups[panel, run, layer_index, label], plot.layers[layer_index]
        cell = cells.index((panel, run if tiled else None))
        row, col = cell // cols + 1, cell % cols + 1
        name, x = config.labels.get(label, label), line.get_column("date").to_list()
        # overlaid, a run has a colour, and its series are named after it
        group, color = (f"{label}|{run}", colors[run]) if overlay else (label, colors[label])

        if by_run:
            group, name = run, runs[run]

        elif overlay:
            name = f"{name} · {runs[run]}"

        # an ensemble's band, but not in a stack: the upper percentile, then the lower one filled up to it
        banded = (line.get_column("low") != line.get_column("high")).any()

        if layer.draw != "stack" and banded:
            for column, quantile in (("high", BAND[1]), ("low", BAND[0])):
                figure.add_trace(go.Scatter(
                    x=x, y=line.get_column(column).to_list(), mode="lines", name=f"{name} {quantile:.0%}",
                    fill="tonexty" if column == "low" else None, legendgroup=group, showlegend=False,
                    line={"color": color, "width": 0},
                ), row=row, col=col)

        trace = go.Scatter(
            x=x, y=line.get_column("value").to_list(), mode="lines", name=name, legendgroup=group,
            showlegend=group not in shown, line={"color": color, "width": _LINE_WIDTH, "dash": layer.dash},
        )

        if layer.draw == "stack":
            trace.update(stackgroup=f"{panel}|{run}|{layer_index}")

        elif layer.draw == "area":
            trace.update(fill="tozeroy")

        shown.add(group)
        figure.add_trace(trace, row=row, col=col)

        # the representative sample over the band, after it so as not to break the band's fill
        if layer.draw != "stack" and banded and line.get_column("representative").is_not_null().any():
            figure.add_trace(go.Scatter(
                x=x, y=line.get_column("representative").to_list(), mode="lines", name=f"{name} representative",
                legendgroup=group, showlegend=False, hoverinfo="skip",
                line={"color": color, "width": _LINE_WIDTH / 2, "dash": "dot"},
            ), row=row, col=col)

    figure.update_layout(
        template="plotly_white", hovermode="x unified", legend={"orientation": "h", "yanchor": "top", "y": -0.08, "x": 0},
    )
    figure.update_yaxes(rangemode="tozero" if plot.from_zero else "normal")
    figure.update_yaxes(title_text=unit, col=1)

    return figure


def _overlays(plot: Plot, series: pl.DataFrame) -> bool:
    """Whether runs can share panels, a colour each: no stack, and no panel's layer has more than one label."""
    return not any(layer.draw == "stack" for layer in plot.layers) and _most_labels(series, "panel", "layer") <= 1


def _most_labels(series: pl.DataFrame, *keys: str) -> int:
    """The most labels a run has in one group of the keys."""
    return series.group_by("run", *keys).agg(pl.col("label").n_unique()).get_column("label").max() or 0


def scale_unit(magnitude: float, unit: str) -> tuple[float, str]:
    """Divisor and unit with a metric prefix that suits the magnitude, e.g. GJ/year to PJ/year."""
    head, slash, tail = unit.partition("/")

    if head not in _SCALABLE or not magnitude:
        return 1.0, unit

    base, power = _SCALABLE[head]
    prefix = max((p for p in _PREFIXES if p <= math.floor(math.log10(magnitude)) + power), default=0)

    return 10.0 ** (prefix - power), _PREFIXES.get(prefix, "") + base + slash + tail


def _grid(titles: list[str], rows: int, cols: int, shared_y: str | bool) -> go.Figure:
    width = 140 // cols  # characters a title line takes before it would run into its neighbour's
    titles = [_wrap(title, width) for title in titles]
    figure = make_subplots(rows=rows, cols=cols, subplot_titles=titles, shared_xaxes=True, shared_yaxes=shared_y)
    figure.update_layout(height=rows * _PANEL_HEIGHT)

    return figure


def _wrap(title: str, width: int) -> str:
    """Break a long title after underscores and spaces into lines of about width characters."""
    lines = [""]

    for part in re.split(r"(?<=[_ ])", title):
        if lines[-1] and len(lines[-1]) + len(part) > width:
            lines.append("")

        lines[-1] += part

    return "<br>".join(line.rstrip() for line in lines)


def _shape(count: int) -> tuple[int, int]:
    rows = max(1, round(math.sqrt(count)))

    return rows, math.ceil(count / rows)


def _rank(config: Config) -> Callable[[str], tuple[int, str]]:
    """Sort key for labels and panels: the canonical order, then alphabetical."""
    rank = {label: i for i, label in enumerate(config.order)}

    return lambda label: (rank.get(label, len(rank)), label)
