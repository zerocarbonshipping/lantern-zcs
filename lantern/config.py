# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Read plots.toml (what to plot) and style.toml (how it looks); a file in ~/.config/lantern/ replaces either."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from importlib.resources import files
from pathlib import Path

USER_DIR = Path.home() / ".config" / "lantern"
_TUPLES = ("series", "transforms")


@dataclass(frozen=True)
class Layer:
    """Series of a plot drawn the same way; plots.toml lists the keys."""

    series: tuple[str, ...]
    kind: str = "line"
    label: str | None = "key1"
    name: str = ""
    transforms: tuple[str, ...] = ()
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
    template: str = "plotly_white"
    height: int = 560
    panel_height: int = 280
    line_width: float = 2.0
    stack_opacity: float = 0.85
    area_opacity: float = 0.3


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
    """Read plots.toml and style.toml, each the user's if present, else the packaged one."""
    plots, style = _read("plots.toml"), _read("style.toml")
    swatches = style.get("swatches", {})

    return Config(
        plots=tuple(_plot(entry) for entry in plots["plots"]),
        labels=plots.get("labels", {}),
        order=tuple(plots.get("order", ())),
        style=Style(
            colors={k: swatches.get(c, c) for k, c in style.get("colors", {}).items()},
            palette=tuple(swatches.get(c, c) for c in style["palette"]),
            **style.get("chart", {}),
        ),
    )


def _read(name: str) -> dict:
    user = USER_DIR / name
    text = user.read_text(encoding="utf-8") if user.is_file() else files("lantern").joinpath(name).read_text("utf-8")

    return tomllib.loads(text)


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
    values = {k: ((v,) if isinstance(v, str) else tuple(v)) if k in _TUPLES else v for k, v in raw.items()}

    if values.get("label") == "none":
        values["label"] = None

    return Layer(**values)
