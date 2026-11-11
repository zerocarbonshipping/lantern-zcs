"""
Read the configuration: plots.yaml and the packaged labels.yaml and theme.yaml.

plots.yaml (what to plot) comes from the working folder or the home folder; the packaged labels.yaml gives the series
names, colours and order and theme.yaml the colours, and plots.yaml can override both entry by entry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, replace
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Any

import plotly.colors
import yaml

if TYPE_CHECKING:
    from collections.abc import Iterable

_TYPED = {"scale", "cumulative", "per_gj", "total", "size", "weight"}
_TEXT = "tag:yaml.org,2002:str"
_PLOT_KEYS = {"title", "unit", "panels", "select_view", "y_axis", "variants", "layers"}
_AXES = {"zero", "fit"}
_VARIANTS = {"lines", "stack"}
_THEME_KEYS = {"swatches", "palette", "font"}
_FONT_KEYS = {"family", "size", "weight", "color"}
_RUNS = "customize_runs"
_LABELS = "labels"
_THEME = "theme"
_NAME_KEYS = {"name", "color"}
_HEX = re.compile(r"#([0-9a-fA-F]{3}){1,2}")
PLOTS_FILES = (Path.cwd() / "plots.yaml", Path.home() / "plots.yaml")


class ConfigError(Exception):
    """A configuration file that Lantern cannot read, or a plot it does not declare."""


@dataclass(frozen=True)
class Layer:
    """Series of a plot drawn the same way; plots.yaml lists the keys."""

    series: tuple[tuple[str, str], ...]
    draw: str = "line"
    split_by: str | None = "key1"
    label: str = ""
    scale: float = 1.0
    line: str | None = None
    cumulative: bool = False
    per_gj: bool = False
    per: tuple[str, str] | None = None


@dataclass(frozen=True)
class Plot:
    """One entry of the catalogue."""

    id: str
    title: str
    section: str
    layers: tuple[Layer, ...]
    unit: str | None = None
    panels: str | None = None
    select_view: str | None = None
    y_axis: str = "zero"


_LAYER_KEYS = {f.name for f in fields(Layer)}


@dataclass(frozen=True)
class Style:
    """How figures look: colours per label and per run, the cycle for the rest, and the font, as Plotly takes it."""

    colors: dict[str, str]
    run_colors: dict[str, str]
    palette: tuple[str, ...]
    font: dict[str, str | float]


@dataclass(frozen=True)
class Config:
    """The plots, the display names and stacking order of the labels, the display names of runs, and the style."""

    plots: tuple[Plot, ...]
    labels: dict[str, str]
    run_names: dict[str, str]
    order: tuple[str, ...]
    style: Style

    def plot(self, plot_id: str) -> Plot:
        """Return the plot with this id."""
        for plot in self.plots:
            if plot.id == plot_id:
                return plot

        raise ConfigError(f"no plot '{plot_id}' in plots.yaml")


def load_config() -> Config:
    """
    Read plots.yaml and the packaged labels.yaml and theme.yaml.

    plots.yaml is the first of PLOTS_FILES there is; labels.yaml and theme.yaml come with the entries it overrides.
    """
    plots = _catalogue()
    runs = _named(plots.pop(_RUNS, None) or {}, f"plots.yaml: {_RUNS}", "run")
    theme = _theme(plots.pop(_THEME, None) or {})
    swatches = theme["swatches"]
    entries = _labels(plots.pop(_LABELS, None) or {})

    for section, section_entries in plots.items():
        if not isinstance(section_entries, dict):
            raise ConfigError(f"plots.yaml: section '{section}' must map plot keys to plots")

    return Config(
        plots=tuple(
            plot
            for section, section_entries in plots.items()
            for key, raw in section_entries.items()
            for plot in _plots(f"{section}_{key}", section.capitalize(), raw)
        ),
        labels={label: value["name"] for label, value in entries if "name" in value},
        run_names={run: value["name"] for run, value in runs.items() if "name" in value},
        order=tuple(label for label, _ in entries),
        style=Style(
            colors=_colors(entries, swatches, "label"),
            run_colors=_colors(runs.items(), swatches, "run"),
            palette=tuple(_color(color, swatches, "theme: palette") for color in theme["palette"]),
            font=theme["font"],
        ),
    )


def _named(raw: object, where: str, what: str) -> dict[str, dict[str, str]]:
    """Entries that name runs or labels, as {name, color} each: a display name alone, or a mapping of name and color."""
    if not isinstance(raw, dict):
        raise ConfigError(f"{where} must map each {what} to a display name or to name and color")

    entries = {key: value if isinstance(value, dict) else {"name": value} for key, value in raw.items()}

    for key, value in entries.items():
        if set(value) - _NAME_KEYS or not all(isinstance(v, str) for v in value.values()):
            raise ConfigError(f"{where}: {what} '{key}' takes a display name, or name and color")

    return entries


def _catalogue() -> dict[str, Any]:
    """Read the entries of the first plots.yaml there is, in the working folder or the home folder."""
    for path in PLOTS_FILES:
        if path.is_file():
            return _read(path.read_text("utf-8"), str(path))

    raise ConfigError(f"no plots.yaml in the working folder or the home folder: {' or '.join(map(str, PLOTS_FILES))}")


def _package(name: str) -> dict[str, Any]:
    return _read(files("lantern").joinpath(name).read_text("utf-8"), name)


def _theme(override: object) -> dict[str, Any]:
    """
    Return the packaged theme with the entries the theme key of plots.yaml overrides.

    Swatches are overridden by name, the palette and the font whole; without any palette, Plotly's own colours are used.
    """
    theme = _package("theme.yaml")

    if not isinstance(override, dict) or set(override) - _THEME_KEYS:
        raise ConfigError(f"plots.yaml: {_THEME} takes {', '.join(sorted(_THEME_KEYS))}")

    swatches = theme.get("swatches", {}) | override.get("swatches", {})

    if not_hex := [name for name, value in swatches.items() if not _HEX.fullmatch(value)]:
        raise ConfigError(f"theme: the swatches {', '.join(not_hex)} are not hex values like #3d5f87")

    palette = override.get("palette") or theme.get("palette") or plotly.colors.qualitative.Plotly
    font = override.get("font") or theme.get("font") or {}

    if not isinstance(font, dict) or set(font) - _FONT_KEYS:
        raise ConfigError(f"theme: font takes {', '.join(sorted(_FONT_KEYS))}")

    return {"swatches": swatches, "palette": palette, "font": font}


def _labels(override: object) -> list[tuple[str, dict[str, str]]]:
    """
    Return the entries of the packaged labels.yaml, (label, {name, color}), in stacking order.

    The labels key of plots.yaml overrides entries by label; a label new there comes after the packaged ones.
    """
    groups = [_named(group, "labels.yaml", "label") for group in _package("labels.yaml").values()]
    entries = [(label, value) for group in groups for label, value in group.items()]
    duplicates = sorted({label for label, _ in entries if sum(other == label for other, _ in entries) > 1})

    if duplicates:
        raise ConfigError(f"labels.yaml lists {', '.join(duplicates)} more than once")

    override = _named(override, f"plots.yaml: {_LABELS}", "label")
    entries = [(label, value | override.get(label, {})) for label, value in entries]
    known = {label for label, _ in entries}

    return entries + [(label, value) for label, value in override.items() if label not in known]


def _read(text: str, name: str) -> dict[str, Any]:
    node = yaml.compose(text)

    if node is None:
        return {}

    _check_text(node, name)
    content = yaml.safe_load(text)

    if not isinstance(content, dict):
        raise ConfigError(f"{name} must map keys to entries")

    return content


def _colors(entries: Iterable[tuple[str, dict[str, str]]], swatches: dict[str, str], what: str) -> dict[str, str]:
    """Return the colours of the entries that give one, as hex, by label or run."""
    return {key: _color(value["color"], swatches, f"{what} '{key}'") for key, value in entries if "color" in value}


def _color(color: str, swatches: dict[str, str], where: str) -> str:
    """Resolve a colour to hex: a hex value, #rgb or #rrggbb, as it is, else the theme's swatch of that name."""
    if _HEX.fullmatch(color):
        return color

    if color not in swatches:
        raise ConfigError(f"{where}: '{color}' is neither a colour name of the theme nor a hex value like #3d5f87")

    return swatches[color]


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


def _plots(plot_id: str, section: str, raw: object) -> list[Plot]:
    """Return an entry's plots: the stack as written, or its variants in order, lines with a panel per label and the stack."""
    if not isinstance(raw, dict):
        raise ConfigError(f"plot '{plot_id}' must map keys to values")

    plot = _plot(plot_id, section, raw)
    variants = raw.get("variants")

    if variants is None:
        return [plot]

    if not isinstance(variants, list) or set(variants) - _VARIANTS or len(set(variants)) < len(variants):
        raise ConfigError(f"plot '{plot_id}': variants must list lines and/or stack once each")

    if not any(layer.draw == "stack" for layer in plot.layers):
        raise ConfigError(f"plot '{plot_id}' has variants but no stack layer")

    layers = tuple(replace(layer, draw="line") if layer.draw == "stack" else layer for layer in plot.layers)
    lines = replace(plot, layers=layers, panels="label", select_view=plot.select_view or plot.panels)
    stacked = replace(plot, id=f"{plot.id}_stacked", title=f"{plot.title} (Stacked)") if "lines" in variants else plot

    return [lines if variant == "lines" else stacked for variant in variants]


def _plot(plot_id: str, section: str, raw: dict[str, Any]) -> Plot:
    layer_keys = _LAYER_KEYS | {"total"}
    unknown = set(raw) - _PLOT_KEYS - layer_keys

    if unknown:
        raise ConfigError(f"plot '{plot_id}' has unknown keys: {', '.join(sorted(unknown))}")

    if "title" not in raw:
        raise ConfigError(f"plot '{plot_id}' has no title")

    layers = raw.get("layers") or [{k: v for k, v in raw.items() if k in layer_keys}]

    if not isinstance(layers, list) or not all(isinstance(layer, dict) for layer in layers):
        raise ConfigError(f"plot '{plot_id}': layers must list layers, each mapping keys to values")
    y_axis = raw.get("y_axis", "zero")

    if y_axis not in _AXES:
        raise ConfigError(f"plot '{plot_id}': y_axis must be zero or fit, not '{y_axis}'")

    return Plot(
        id=plot_id,
        title=raw["title"],
        section=section,
        layers=tuple(_layer(plot_id, layer) for layer in layers),
        unit=raw.get("unit"),
        panels=raw.get("panels"),
        select_view=raw.get("select_view"),
        y_axis=y_axis,
    )


def _layer(plot_id: str, raw: dict[str, Any]) -> Layer:
    values = dict(raw)
    total = values.pop("total", False)
    unknown = set(values) - _LAYER_KEYS

    if unknown:
        raise ConfigError(f"a layer of plot '{plot_id}' has unknown keys: {', '.join(sorted(unknown))}")

    if total and "split_by" in values:
        raise ConfigError(f"a layer of plot '{plot_id}' has both total and split_by")

    if "series" not in values:
        raise ConfigError(f"a layer of plot '{plot_id}' has no series")

    series = values["series"]
    values["series"] = tuple(_series(plot_id, s) for s in ([series] if isinstance(series, str) else series))

    if "per" in values:
        if values.get("cumulative"):
            raise ConfigError(f"a layer of plot '{plot_id}' has both cumulative and per")

        values["per"] = _series(plot_id, values["per"])

    if total:
        values["split_by"] = None

    return Layer(**values)


def _series(plot_id: str, series: str) -> tuple[str, str]:
    """Split a series "kind.attribute" into (kind, attribute)."""
    kind, _, attribute = series.partition(".") if isinstance(series, str) else ("", "", "")

    if not kind or not attribute:
        raise ConfigError(f"plot '{plot_id}': series '{series}' is not 'kind.attribute'")

    return kind, attribute
