# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Draw prepared series as a Plotly figure: one panel per facet value, and per run when several are loaded."""

from __future__ import annotations

import math

import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots

from lantern.config import Config, Plot

SEPARATOR = " - "

# unit head to (base unit, power of ten of the head, prefixes as words)
_SCALABLE = {
    "GJ": ("J", 9, False), "MJ": ("J", 6, False), "J": ("J", 0, False), "t": ("t", 0, False),
    "tCO2e": ("tCO2e", 0, False), "MW": ("W", 6, False), "W": ("W", 0, False), "USD": ("USD", 0, True),
    "cargo-miles": ("cargo-miles", 0, True), "vessels": ("vessels", 0, True),
}
_SYMBOLS = {3: "k", 6: "M", 9: "G", 12: "T", 15: "P", 18: "E"}
_WORDS = {3: "thousand", 6: "million", 9: "billion", 12: "trillion", 15: "quadrillion", 18: "quintillion"}


def build(plot: Plot, series: pl.DataFrame, unit: str, config: Config) -> go.Figure:
    """Draw one plot."""
    magnitude = series.select(pl.col("value").fill_nan(None).abs().max()).item() if series.height else 0.0
    divisor, unit = scale_unit(magnitude or 0.0, unit)
    series = series.with_columns(value=pl.col("value") / divisor)

    if series.get_column("run").n_unique() > 1:
        panel, run = pl.col("panel"), pl.col("run")
        series = series.with_columns(panel=pl.when(panel == "").then(run).otherwise(panel + SEPARATOR + run))

    panels = _ordered(series.get_column("panel").unique().to_list(), config)
    labels = sorted(series.get_column("label").unique().to_list())
    style = config.style
    free = iter(style.palette * (len(labels) // len(style.palette) + 1))
    colors = {label: style.colors.get(label) or next(free) for label in labels}
    figure = _grid(panels, config)
    shown = set()

    for index, panel in enumerate(panels):
        cell = _cell(index, len(panels))

        for layer_index, layer in enumerate(plot.layers):
            part = series.filter((pl.col("panel") == panel) & (pl.col("layer") == layer_index))

            for label in _ordered(part.get_column("label").unique().to_list(), config):
                line = part.filter(pl.col("label") == label)
                trace = go.Scatter(
                    x=line.get_column("date").to_list(), y=line.get_column("value").to_list(), mode="lines",
                    name=config.labels.get(label, label), legendgroup=label, showlegend=label not in shown,
                    line={"color": colors[label], "width": style.line_width, "dash": layer.dash},
                )

                if layer.kind == "stack":
                    fill = _rgba(colors[label], style.stack_opacity)
                    trace.update(stackgroup=f"{panel}|{layer_index}", line_width=0.5, fillcolor=fill)

                elif layer.kind == "area":
                    trace.update(fill="tozeroy", fillcolor=_rgba(colors[label], style.area_opacity))

                shown.add(label)
                figure.add_trace(trace, row=cell[0], col=cell[1])

    figure.update_layout(
        template=style.template, hovermode="x unified", margin={"l": 70, "r": 30, "t": 50, "b": 40},
        legend={"orientation": "h", "yanchor": "top", "y": -0.08, "x": 0},
    )
    figure.update_yaxes(rangemode=plot.rangemode)
    figure.update_yaxes(title_text=unit, col=1)

    return figure


def scale_unit(magnitude: float, unit: str) -> tuple[float, str]:
    """Divisor and unit with a metric prefix that suits the magnitude, e.g. GJ/year to PJ/year."""
    head, slash, tail = unit.partition("/")

    if head not in _SCALABLE or not magnitude or not math.isfinite(magnitude):
        return 1.0, unit

    base, power, words = _SCALABLE[head]
    prefix = max((p for p in _SYMBOLS if p <= math.floor(math.log10(magnitude)) + power), default=0)
    label = (f"{_WORDS[prefix]} {base}" if prefix else base) if words else f"{_SYMBOLS.get(prefix, '')}{base}"

    return 10.0 ** (prefix - power), label + slash + tail


def _grid(panels: list[str], config: Config) -> go.Figure:
    titles = [SEPARATOR.join(config.labels.get(p, p) for p in panel.split(SEPARATOR)) for panel in panels]
    rows, cols = _shape(len(panels))

    figure = make_subplots(rows=rows, cols=cols, subplot_titles=titles, shared_xaxes=True,
                           horizontal_spacing=min(0.08, 0.6 / cols), vertical_spacing=min(0.12, 0.6 / rows))

    figure.update_layout(height=max(config.style.height, rows * config.style.panel_height))

    return figure


def _shape(count: int) -> tuple[int, int]:
    rows = max(1, round(math.sqrt(count)))

    return rows, math.ceil(count / rows)


def _cell(index: int, count: int) -> tuple[int, int]:
    cols = _shape(count)[1]

    return index // cols + 1, index % cols + 1


def _ordered(labels: list[str], config: Config) -> list[str]:
    rank = {label: i for i, label in enumerate(config.order)}

    return sorted(labels, key=lambda label: (rank.get(label, len(rank)), label))


def _rgba(color: str, alpha: float) -> str:
    red, green, blue = (int(color[i:i + 2], 16) for i in (1, 3, 5))

    return f"rgba({red},{green},{blue},{alpha})"
