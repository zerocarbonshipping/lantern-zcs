# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Read the packaged plots.yaml (what to plot) and labels.yaml (series names, colours and order), and the theme."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from importlib.resources import files
from pathlib import Path

import plotly.colors
import yaml

# keys whose values are numbers or true/false; YAML reads every other value as text
_TYPED = {"weight", "scale", "unstack", "cumulative", "per_energy", "total", "from_zero"}
_TEXT = "tag:yaml.org,2002:str"
_PLOT_KEYS = {"title", "unit", "panels", "views", "from_zero", "unstack", "weight", "layers"}
_THEME_KEYS = {"swatches", "palette"}
# the Center's theme, in the repository next to the package but not part of it
_THEME = Path(__file__).resolve().parent.parent / "theme.yaml"


class ConfigError(ValueError):
    """A configuration file that Lantern cannot read."""


@dataclass(frozen=True)
class Layer:
    """Series of a plot drawn the same way; plots.yaml lists the keys."""

    series: tuple[tuple[str, str], ...]
    draw: str = "line"
    by: str | None = "key1"
    name: str = ""
    scale: float = 1.0
    dash: str | None = None
    cumulative: bool = False
    per_energy: bool = False


@dataclass(frozen=True)
class Plot:
    """One entry of the catalogue."""

    id: str
    title: str
    section: str
    layers: tuple[Layer, ...]
    unit: str | None = None
    panels: str | None = None
    views: str | None = None
    from_zero: bool = True
    weight: float = 0.0


@dataclass(frozen=True)
class Style:
    """How figures look: colours per label and the cycle for the rest."""

    colors: dict[str, str]
    palette: tuple[str, ...]


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
    """Read plots.yaml, labels.yaml and the theme, if there is one."""
    plots, labels, theme = _package("plots.yaml"), _package("labels.yaml"), _theme()
    swatches = theme.get("swatches", {})
    # the groups only organise the file; the order of the labels in it is the stacking order
    entries = [(label, value) for group in labels.values() for label, value in group.items()]
    entries = [(label, value if isinstance(value, dict) else {"name": value}) for label, value in entries]
    duplicates = sorted({label for label, _ in entries if sum(other == label for other, _ in entries) > 1})

    if duplicates:
        raise ConfigError(f"labels.yaml lists {', '.join(duplicates)} more than once")

    return Config(
        plots=tuple(
            plot for section, entries_ in plots.items() for key, raw in entries_.items()
            for plot in _plots(f"{section}_{key}", section.capitalize(), raw)
        ),
        labels={label: value["name"] for label, value in entries if "name" in value},
        order=tuple(label for label, _ in entries),
        style=Style(
            colors={label: color for label, value in entries if (color := _color(value.get("color"), swatches))},
            # without a theme, Plotly's own colours
            palette=tuple(_color(c, swatches) or c for c in theme.get("palette", plotly.colors.qualitative.Plotly)),
        ),
    )


def _package(name: str) -> dict:
    return _read(files("lantern").joinpath(name).read_text("utf-8"), name)


def _theme() -> dict:
    if not _THEME.is_file():
        return {}

    text = _THEME.read_text("utf-8")
    unknown = set(yaml.safe_load(text) or {}) - _THEME_KEYS

    if unknown:
        raise ConfigError(f"{_THEME} has unknown keys: {', '.join(sorted(unknown))}")

    return _read(text, str(_THEME)) or {}


def _read(text: str, name: str) -> dict:
    _check_text(yaml.compose(text), name)

    return yaml.safe_load(text)


def _color(color: str | None, swatches: dict[str, str]) -> str | None:
    """A label's colour: a swatch of the theme or a hex value; a swatch without a theme is left to the palette."""
    if color is None or color.startswith("#"):
        return color

    return swatches.get(color)


def _check_text(node: yaml.Node, name: str, key: str | None = None) -> None:
    """Stop at an unquoted value YAML reads as other than text, such as no, on or 2030, where text is meant."""
    if isinstance(node, yaml.ScalarNode):
        if node.style is None and node.tag != _TEXT and key not in _TYPED:
            kind = node.tag.rsplit(":", 1)[1]
            raise ConfigError(f"{name}, line {node.start_mark.line + 1}: '{node.value}' reads as {kind}; quote it")

        return

    if isinstance(node, yaml.SequenceNode):
        for item in node.value:
            _check_text(item, name, key)

    elif isinstance(node, yaml.MappingNode):
        for item_key, value in node.value:
            _check_text(item_key, name)
            _check_text(value, name, item_key.value)


def _plots(plot_id: str, section: str, raw: dict) -> list[Plot]:
    """An entry's plot; one with unstack: true is first drawn as lines, a panel per label, then as its stack."""
    plot = _plot(plot_id, section, raw)

    if not raw.get("unstack"):
        return [plot]

    # the stack's panels move to the views, as the lines' panels are the labels
    layers = tuple(replace(layer, draw="line") if layer.draw == "stack" else layer for layer in plot.layers)
    lines = replace(plot, layers=layers, panels="label", views=plot.views or plot.panels)
    # the lines' weight alone counts in choosing the representative
    stacked = replace(plot, id=f"{plot.id}_stacked", title=f"{plot.title} (Stacked)", weight=0.0)

    return [lines, stacked]


def _plot(plot_id: str, section: str, raw: dict) -> Plot:
    layer_keys = {f.name for f in fields(Layer)} | {"total"}
    unknown = set(raw) - _PLOT_KEYS - layer_keys

    if unknown:
        raise ConfigError(f"plot '{plot_id}' has unknown keys: {', '.join(sorted(unknown))}")

    layers = raw.get("layers") or [{k: v for k, v in raw.items() if k in layer_keys}]

    return Plot(
        id=plot_id,
        title=raw["title"],
        section=section,
        layers=tuple(_layer(plot_id, layer) for layer in layers),
        unit=raw.get("unit"),
        panels=raw.get("panels"),
        views=raw.get("views"),
        from_zero=raw.get("from_zero", True),
        weight=float(raw.get("weight", 0.0)),
    )


def _layer(plot_id: str, raw: dict) -> Layer:
    values = dict(raw)
    total = values.pop("total", False)
    unknown = set(values) - {f.name for f in fields(Layer)}

    if unknown:
        raise ConfigError(f"a layer of plot '{plot_id}' has unknown keys: {', '.join(sorted(unknown))}")

    if total and "by" in values:
        raise ConfigError(f"a layer of plot '{plot_id}' has both total and by")

    series = values["series"]
    values["series"] = tuple(_series(plot_id, s) for s in ([series] if isinstance(series, str) else series))

    if total:
        values["by"] = None

    return Layer(**values)


def _series(plot_id: str, series: str) -> tuple[str, str]:
    """A series "kind.attribute" as (kind, attribute)."""
    kind, _, attribute = series.partition(".")

    if not kind or not attribute:
        raise ConfigError(f"plot '{plot_id}': series '{series}' is not 'kind.attribute'")

    return kind, attribute
