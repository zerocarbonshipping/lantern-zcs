# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Draw prepared series as a Plotly figure: one panel per facet value, and per run when several are loaded."""

from __future__ import annotations

import math
from collections.abc import Callable

import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots

from lantern.config import Config, Plot

SEPARATOR = " - "

# unit head to (base unit, power of ten of the head); counts and money keep their unit, plotly's ticks scale them
_SCALABLE = {"GJ": ("J", 9), "MJ": ("J", 6), "J": ("J", 0), "t": ("t", 0), "tCO2e": ("tCO2e", 0), "MW": ("W", 6), "W": ("W", 0)}
_PREFIXES = {3: "k", 6: "M", 9: "G", 12: "T", 15: "P", 18: "E"}


def build(plot: Plot, series: pl.DataFrame, unit: str, config: Config) -> go.Figure:
    """Draw one plot."""
    divisor, unit = scale_unit(series.select(pl.col("value").abs().max()).item() or 0.0, unit)
    series = series.with_columns(value=pl.col("value") / divisor)

    # a panel is a facet value and a run; the run is named only when several are loaded
    several = series.get_column("run").n_unique() > 1
    rank = _rank(config)
    panels = sorted(series.select("panel", "run").unique().rows(), key=lambda p: (rank(p[0]), p[1]))
    titles = [SEPARATOR.join(filter(None, (config.labels.get(p, p), run if several else ""))) for p, run in panels]
    labels = sorted(series.get_column("label").unique().to_list())
    style = config.style
    free = iter(style.palette * (len(labels) // len(style.palette) + 1))
    colors = {label: style.colors.get(label) or next(free) for label in labels}
    figure = _grid(titles, config)
    shown = set()

    # traces go in panel, layer and label order, which sets the stacking and the legend
    groups = series.partition_by("panel", "run", "layer", "label", as_dict=True)
    order = sorted(groups, key=lambda k: (panels.index(k[:2]), k[2], rank(k[3])))

    for panel, run, layer_index, label in order:
        line, layer = groups[panel, run, layer_index, label], plot.layers[layer_index]
        trace = go.Scatter(
            x=line.get_column("date").to_list(), y=line.get_column("value").to_list(), mode="lines",
            name=config.labels.get(label, label), legendgroup=label, showlegend=label not in shown,
            line={"color": colors[label], "width": style.line_width, "dash": layer.dash},
        )

        if layer.kind == "stack":
            trace.update(stackgroup=f"{panel}|{run}|{layer_index}")

        elif layer.kind == "area":
            trace.update(fill="tozeroy")

        shown.add(label)
        row, col = _cell(panels.index((panel, run)), len(panels))
        figure.add_trace(trace, row=row, col=col)

    figure.update_layout(
        template=style.template, hovermode="x unified", legend={"orientation": "h", "yanchor": "top", "y": -0.08, "x": 0},
    )
    figure.update_yaxes(rangemode=plot.rangemode)
    figure.update_yaxes(title_text=unit, col=1)

    return figure


def scale_unit(magnitude: float, unit: str) -> tuple[float, str]:
    """Divisor and unit with a metric prefix that suits the magnitude, e.g. GJ/year to PJ/year."""
    head, slash, tail = unit.partition("/")

    if head not in _SCALABLE or not magnitude:
        return 1.0, unit

    base, power = _SCALABLE[head]
    prefix = max((p for p in _PREFIXES if p <= math.floor(math.log10(magnitude)) + power), default=0)

    return 10.0 ** (prefix - power), _PREFIXES.get(prefix, "") + base + slash + tail


def _grid(titles: list[str], config: Config) -> go.Figure:
    rows, cols = _shape(len(titles))
    figure = make_subplots(rows=rows, cols=cols, subplot_titles=titles, shared_xaxes=True)
    figure.update_layout(height=rows * config.style.panel_height)

    return figure


def _shape(count: int) -> tuple[int, int]:
    rows = max(1, round(math.sqrt(count)))

    return rows, math.ceil(count / rows)


def _cell(index: int, count: int) -> tuple[int, int]:
    cols = _shape(count)[1]

    return index // cols + 1, index % cols + 1


def _rank(config: Config) -> Callable[[str], tuple[int, str]]:
    """Sort key for labels and panels: the canonical order, then alphabetical."""
    rank = {label: i for i, label in enumerate(config.order)}

    return lambda label: (rank.get(label, len(rank)), label)
