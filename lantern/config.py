# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Read the packaged plots.toml (what to plot) and style.toml (how it looks)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields, replace
from importlib.resources import files


@dataclass(frozen=True)
class Layer:
    """Series of a plot drawn the same way; plots.toml lists the keys."""

    series: tuple[str, ...]
    kind: str = "line"
    label: str | None = "key1"
    name: str = ""
    scale: float = 1.0
    dash: str | None = None


@dataclass(frozen=True)
class Plot:
    """One entry of the catalogue."""

    id: str
    title: str
    section: str
    layers: tuple[Layer, ...]
    unit: str | None = None
    facet: str | None = None
    split: str | None = None
    rangemode: str = "tozero"


@dataclass(frozen=True)
class Style:
    """How figures look: colours per label, the fallback cycle and chart settings."""

    colors: dict[str, str]
    palette: tuple[str, ...]
    panel_height: int = 280
    line_width: float = 2.0


@dataclass(frozen=True)
class Config:
    """The plots with their display names and stacking order, and the style."""

    plots: tuple[Plot, ...]
    labels: dict[str, str]
    order: tuple[str, ...]
    style: Style

    def plot(self, plot_id: str) -> Plot:
        """The plot with this id."""
        for plot in self.plots:
            if plot.id == plot_id:
                return plot

        raise KeyError(plot_id)


def load_config() -> Config:
    """Read plots.toml and style.toml."""
    plots, style = _read("plots.toml"), _read("style.toml")
    swatches = style.get("swatches", {})

    return Config(
        plots=tuple(plot for entry in plots["plots"] for plot in _plots(entry)),
        labels=plots.get("labels", {}),
        order=tuple(plots.get("order", ())),
        style=Style(
            colors={k: swatches.get(c, c) for k, c in style.get("colors", {}).items()},
            palette=tuple(swatches.get(c, c) for c in style["palette"]),
            **style.get("chart", {}),
        ),
    )


def _read(name: str) -> dict:
    return tomllib.loads(files("lantern").joinpath(name).read_text("utf-8"))


def _plots(raw: dict) -> list[Plot]:
    """An entry's plot; one with unstack = true is first drawn as lines, a panel per label, then as its stack."""
    plot = _plot(raw)

    if not raw.get("unstack"):
        return [plot]

    # a facet the stack has moves to the views, as the lines' panels are the labels
    layers = tuple(replace(layer, kind="line") if layer.kind == "stack" else layer for layer in plot.layers)
    lines = replace(plot, layers=layers, facet="label", split=plot.split or plot.facet)
    stacked = replace(plot, id=f"{plot.id}_stacked", title=f"{plot.title} (Stacked)")

    return [lines, stacked]


def _plot(raw: dict) -> Plot:
    layer_keys = {f.name for f in fields(Layer)}
    layers = raw.get("layers") or [{k: v for k, v in raw.items() if k in layer_keys}]

    return Plot(
        id=raw["id"],
        title=raw["title"],
        section=raw["section"],
        layers=tuple(_layer(layer) for layer in layers),
        unit=raw.get("unit"),
        facet=raw.get("facet"),
        split=raw.get("split"),
        rangemode=raw.get("rangemode", "tozero"),
    )


def _layer(raw: dict) -> Layer:
    series = raw["series"]
    values = {**raw, "series": (series,) if isinstance(series, str) else tuple(series)}

    if values.get("label") == "none":
        values["label"] = None

    return Layer(**values)
