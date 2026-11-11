"""
Draw the prepared lines of one or more runs as a Plotly figure, one panel per value of the plot's panels.

Several runs share the panels in a colour each where colour tells nothing else, that is where no panel's layer has more
than one label; stacks and the other plots get a column of panels per run. A line with a summary gets its band, low to
high, and its median dashed, except in a stack, where percentiles do not add up.
"""

from __future__ import annotations

import itertools
import math
import re
from typing import TYPE_CHECKING

import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots

from lantern import data

if TYPE_CHECKING:
    from collections.abc import Callable

    from lantern.config import Config, Plot, Style

# counts and money keep their unit; plotly's ticks scale them
_SCALABLE = {"GJ": ("J", 9), "MJ": ("J", 6), "J": ("J", 0), "t": ("t", 0), "tCO2e": ("tCO2e", 0), "MW": ("W", 6), "W": ("W", 0)}
_PREFIXES = {3: "k", 6: "M", 9: "G", 12: "T", 15: "P", 18: "E"}
_PANEL_HEIGHT = 280  # px per row of panels
_LINE_WIDTH = 2.0
_BAND_ALPHA = 0.2


def build(
    plot: Plot,
    series: pl.DataFrame,
    unit: str,
    config: Config,
    runs: dict[str, str],
    panel: str | None = None,
) -> go.Figure:
    """Draw one plot of the runs, named in order in runs, or only the given panel, enlarged."""
    rank = _rank(config)
    style = config.style
    free = itertools.cycle(style.palette)
    run_colors = {run: _run_color(run, style) or next(free) for run in runs}
    present = set(series.get_column("run").unique().to_list())
    runs = {run: name for run, name in runs.items() if run in present}
    panels = panels_of(series, config)
    labels = sorted(series.get_column("label").unique().to_list())
    overlay = len(runs) > 1 and _overlays(plot, series)
    tiled = len(runs) > 1 and not overlay
    by_run = overlay and _most_labels(series, "panel") <= 1

    if overlay:
        colors = run_colors

    else:
        free = itertools.cycle(style.palette)
        colors = {label: style.colors.get(label) or next(free) for label in labels}

    meta = [[p, config.labels.get(p, p)] for p in panels]

    if panel in panels:
        series, panels = series.filter(pl.col("panel") == panel), [panel]

    divisor, unit = _scale_unit(series.select(pl.col("value").abs().max()).item() or 0.0, unit)
    series = series.with_columns(pl.col("value", *data.SUMMARY) / divisor)

    columns = list(runs) if tiled else [None]
    cells = [(p, run) for p in panels for run in columns]
    rows, cols = (len(panels), len(columns)) if tiled and len(panels) > 1 else _shape(len(cells))
    titles = [" · ".join(filter(None, (config.labels.get(p, p), runs[run] if run else None))) for p, run in cells]
    figure = _grid(titles, rows, cols, ("rows" if len(panels) > 1 else "all") if tiled else False)
    # the page reads the panels, the panel of each cell and the run colours from meta
    figure.update_layout(meta={"panels": meta, "cells": [p for p, _ in cells], "colors": run_colors})
    shown = set()

    # traces go in panel, run, layer and label order, which sets the stacking and the legend
    groups = series.partition_by("panel", "run", "layer", "label", as_dict=True)
    order = sorted(groups, key=lambda k: (panels.index(k[0]), list(runs).index(k[1]), k[2], rank(k[3])))

    for panel, run, layer_index, label in order:
        line, layer = groups[panel, run, layer_index, label], plot.layers[layer_index]
        cell = cells.index((panel, run if tiled else None))
        row, col = cell // cols + 1, cell % cols + 1
        name, x = config.labels.get(label, label), line.get_column("date").to_list()
        group, color = (f"{label}|{run}", colors[run]) if overlay else (label, colors[label])

        if by_run:
            group, name = run, runs[run]

        elif overlay:
            name = f"{name} · {runs[run]}"

        trace = go.Scatter(
            x=x,
            y=line.get_column("value").to_list(),
            mode="lines",
            name=name,
            legendgroup=group,
            showlegend=group not in shown,
            line={"color": color, "width": _LINE_WIDTH, "dash": layer.line},
        )

        if layer.draw == "stack":
            trace.update(stackgroup=f"{panel}|{run}|{layer_index}")

        elif layer.draw == "area":
            trace.update(fill="tozeroy")

        # the band goes under the line, as two traces in a row, the second filled to the first; the median over it
        elif line.get_column("low").is_not_null().any():
            for trace_ in _summary_traces(line, name, group, color):
                figure.add_trace(trace_, row=row, col=col)

        shown.add(group)
        figure.add_trace(trace, row=row, col=col)

    figure.update_layout(
        template="plotly_white",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "top", "y": -0.08, "x": 0},
        font=style.font,
    )
    # r, not g: no exponent notation for USD in the billions
    figure.update_yaxes(rangemode="tozero" if plot.y_axis == "zero" else "normal", hoverformat=",.3~r")
    figure.update_yaxes(title_text=unit, col=1)

    return figure


def _summary_traces(line: pl.DataFrame, name: str, group: str, color: str) -> list[go.Scatter]:
    """Return the band of a line, low to high, and its median, dashed; they toggle with the line in the legend."""
    x = line.get_column("date").to_list()
    edge = {"x": x, "mode": "lines", "line": {"width": 0, "color": color}, "legendgroup": group, "showlegend": False}

    return [
        go.Scatter(y=line.get_column("high").to_list(), name=f"{name} high", hoverinfo="skip", **edge),
        go.Scatter(
            y=line.get_column("low").to_list(),
            name=f"{name} low",
            fill="tonexty",
            fillcolor=_rgba(color),
            hoverinfo="skip",
            **edge,
        ),
        go.Scatter(
            x=x,
            y=line.get_column("median").to_list(),
            mode="lines",
            name=f"{name} median",
            legendgroup=group,
            showlegend=False,
            line={"color": color, "width": _LINE_WIDTH / 2, "dash": "dash"},
        ),
    ]


def _rgba(color: str, alpha: float = _BAND_ALPHA) -> str:
    """Convert a hex colour, #rgb or #rrggbb, to rgba with the alpha."""
    digits = color[1:] if len(color) == 7 else "".join(c * 2 for c in color[1:])
    r, g, b = (int(digits[i : i + 2], 16) for i in (0, 2, 4))

    return f"rgba({r}, {g}, {b}, {alpha})"


def panels_of(series: pl.DataFrame, config: Config) -> list[str]:
    """Return the panels of prepared lines, in the canonical order of the labels."""
    return sorted(series.get_column("panel").unique().to_list(), key=_rank(config))


def table(series: pl.DataFrame, config: Config, runs: dict[str, str], panel: str | None = None) -> str:
    """
    Return the lines of a figure as CSV, a row per value: run, panel, label, date, value.

    They are named as displayed and in the figure's order; the values are as the file holds them, in the plot's unit.
    """
    if panel is not None:
        series = series.filter(pl.col("panel") == panel)

    names = {"run": runs, "panel": config.labels, "label": config.labels}

    if series.is_empty():
        return ",".join((*names, "date", "value")) + "\n"

    summary = [c for c in data.SUMMARY if series.get_column(c).is_not_null().any()]
    named = [pl.col(k).replace_strict(v, default=pl.col(k)).cast(pl.String) for k, v in names.items()]

    return series.sort("layer").with_columns(named).select(*names, "date", "value", *summary).write_csv()


def _run_color(run: str, style: Style) -> str | None:
    """Return the colour plots.yaml gives a run: by its id, else by its name within its compiled file."""
    return style.run_colors.get(run) or style.run_colors.get(run.partition("/")[2] or run)


def _overlays(plot: Plot, series: pl.DataFrame) -> bool:
    """Whether runs can share panels, a colour each: no stack, and no panel's layer has more than one label."""
    return not any(layer.draw == "stack" for layer in plot.layers) and _most_labels(series, "panel", "layer") <= 1


def _most_labels(series: pl.DataFrame, *keys: str) -> int:
    """Count the most labels a run has in one group of the keys."""
    most: int | None = series.group_by("run", *keys).agg(pl.col("label").n_unique()).select(pl.col("label").max()).item()

    return most or 0


def _scale_unit(magnitude: float, unit: str) -> tuple[float, str]:
    """Divisor and unit with a metric prefix that suits the magnitude, e.g. GJ/year to PJ/year."""
    head, slash, tail = unit.partition("/")

    if head not in _SCALABLE or not magnitude:
        return 1.0, unit

    base, power = _SCALABLE[head]
    prefix = max((p for p in _PREFIXES if p <= math.floor(math.log10(magnitude)) + power), default=0)

    return 10.0 ** (prefix - power), _PREFIXES.get(prefix, "") + base + slash + tail


def _grid(titles: list[str], rows: int, cols: int, shared_y: str | bool) -> go.Figure:
    width = 140 // cols  # characters across the figure
    titles = [_wrap(title, width) for title in titles]
    figure = make_subplots(rows=rows, cols=cols, subplot_titles=titles, shared_xaxes=True, shared_yaxes=shared_y)
    lines = max((title.count("<br>") + 1 for title in titles if title), default=0)
    figure.update_layout(height=rows * _PANEL_HEIGHT, margin={"t": 16 + 24 * lines})

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
    """Return the rows and columns of a grid of about square cells; no panels, as of runs without data, get one empty."""
    rows = max(1, round(math.sqrt(count)))

    return rows, max(1, math.ceil(count / rows))


def _rank(config: Config) -> Callable[[str], tuple[int, str]]:
    """Sort key for labels and panels: the canonical order, then alphabetical."""
    rank = {label: i for i, label in enumerate(config.order)}

    return lambda label: (rank.get(label, len(rank)), label)
