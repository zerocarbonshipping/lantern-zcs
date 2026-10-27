# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Read plots.yaml (what to plot) from the working folder or the home folder, and the packaged labels.yaml (series names,
colours and order) and theme.yaml (the colours), which plots.yaml can override entry by entry."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from importlib.resources import files
from pathlib import Path

import plotly.colors
import yaml

# keys whose values are numbers or true/false; YAML reads every other value as text
_TYPED = {"scale", "cumulative", "per_gj", "total"}
_TEXT = "tag:yaml.org,2002:str"
_PLOT_KEYS = {"title", "unit", "panels", "select_view", "y_axis", "variants", "layers"}
_AXES = {"zero", "fit"}
_VARIANTS = {"lines", "stack"}
_THEME_KEYS = {"swatches", "palette"}
# the keys of plots.yaml that are not sections: the display names and colours of runs, and overrides of entries of
# labels.yaml and theme.yaml
_RUNS = "customize_runs"
_LABELS = "labels"
_THEME = "theme"
_RUN_KEYS = {"name", "color"}
_LABEL_KEYS = {"name", "color"}
# where plots.yaml is looked for, in order
PLOTS_FILES = (Path.cwd() / "plots.yaml", Path.home() / "plots.yaml")


class ConfigError(ValueError):
    """A configuration file that Lantern cannot read."""


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


@dataclass(frozen=True)
class Style:
    """How figures look: colours per label and per run, and the cycle for the rest."""

    colors: dict[str, str]
    run_colors: dict[str, str]
    palette: tuple[str, ...]


@dataclass(frozen=True)
class Config:
    """The plots, the display names and stacking order of the labels, the display names of runs, and the style."""

    plots: tuple[Plot, ...]
    labels: dict[str, str]
    run_names: dict[str, str]
    order: tuple[str, ...]
    style: Style

    def plot(self, plot_id: str) -> Plot:
        """The plot with this id."""
        for plot in self.plots:
            if plot.id == plot_id:
                return plot

        raise KeyError(plot_id)


def load_config() -> Config:
    """Read plots.yaml, the first of PLOTS_FILES there is, and the packaged labels.yaml and theme.yaml, with the
    entries plots.yaml overrides."""
    plots = _plots_file()
    runs = _runs(plots.pop(_RUNS, None) or {})
    theme = _theme(plots.pop(_THEME, None) or {})
    swatches = theme["swatches"]
    entries = _labels(plots.pop(_LABELS, None) or {})

    return Config(
        plots=tuple(
            plot for section, entries_ in plots.items() for key, raw in entries_.items()
            for plot in _plots(f"{section}_{key}", section.capitalize(), raw)
        ),
        labels={label: value["name"] for label, value in entries if "name" in value},
        run_names={run: value["name"] for run, value in runs.items() if "name" in value},
        order=tuple(label for label, _ in entries),
        style=Style(
            colors={label: color for label, value in entries if (color := _color(value.get("color"), swatches))},
            run_colors={run: color for run, value in runs.items() if (color := _color(value.get("color"), swatches))},
            palette=tuple(_color(c, swatches) or c for c in theme["palette"]),
        ),
    )


def _runs(raw: object) -> dict[str, dict]:
    """The runs entry of plots.yaml: each run's display name, or its name and colour."""
    if not isinstance(raw, dict):
        raise ConfigError(f"plots.yaml: {_RUNS} must map run names to a display name or to name and color")

    runs = {run: value if isinstance(value, dict) else {"name": value} for run, value in raw.items()}

    for run, value in runs.items():
        if set(value) - _RUN_KEYS or not all(isinstance(v, str) for v in value.values()):
            raise ConfigError(f"plots.yaml: run '{run}' takes a display name, or name and color")

    return runs


def _plots_file() -> dict:
    """The entries of the first plots.yaml there is, in the working folder or the home folder."""
    for path in PLOTS_FILES:
        if path.is_file():
            return _read(path.read_text("utf-8"), str(path)) or {}

    raise ConfigError(f"no plots.yaml in the working folder or the home folder: {' or '.join(map(str, PLOTS_FILES))}")


def _package(name: str) -> dict:
    return _read(files("lantern").joinpath(name).read_text("utf-8"), name) or {}


def _theme(override: object) -> dict:
    """The packaged theme with the entries the theme key of plots.yaml overrides: swatches by name, the palette whole;
    without any palette, Plotly's own colours."""
    theme = _package("theme.yaml")

    if not isinstance(override, dict) or set(override) - _THEME_KEYS:
        raise ConfigError(f"plots.yaml: {_THEME} takes {' and '.join(sorted(_THEME_KEYS))}")

    swatches = theme.get("swatches", {}) | override.get("swatches", {})
    palette = override.get("palette") or theme.get("palette") or plotly.colors.qualitative.Plotly

    return {"swatches": swatches, "palette": palette}


def _labels(override: object) -> list[tuple[str, dict]]:
    """The entries of the packaged labels.yaml, (label, {name, color}), in stacking order, with those the labels key of
    plots.yaml overrides, by label; a label new there comes after the packaged ones."""
    labels = _package("labels.yaml")
    # the groups only organise the file; the order of the labels in it is the stacking order
    entries = [(label, value) for group in labels.values() for label, value in group.items()]
    entries = [(label, value if isinstance(value, dict) else {"name": value}) for label, value in entries]
    duplicates = sorted({label for label, _ in entries if sum(other == label for other, _ in entries) > 1})

    if duplicates:
        raise ConfigError(f"labels.yaml lists {', '.join(duplicates)} more than once")

    if not isinstance(override, dict):
        raise ConfigError(f"plots.yaml: {_LABELS} must map labels to a display name or to name and color")

    override = {label: value if isinstance(value, dict) else {"name": value} for label, value in override.items()}

    for label, value in override.items():
        if set(value) - _LABEL_KEYS or not all(isinstance(v, str) for v in value.values()):
            raise ConfigError(f"plots.yaml: label '{label}' takes a display name, or name and color")

    entries = [(label, value | override.get(label, {})) for label, value in entries]
    known = {label for label, _ in entries}

    return entries + [(label, value) for label, value in override.items() if label not in known]


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
    """An entry's plots: the stack as written, or its variants in order, lines with a panel per label and the stack."""
    plot = _plot(plot_id, section, raw)
    variants = raw.get("variants")

    if variants is None:
        return [plot]

    if not isinstance(variants, list) or set(variants) - _VARIANTS or len(set(variants)) < len(variants):
        raise ConfigError(f"plot '{plot_id}': variants must list lines and/or stack once each")

    if not any(layer.draw == "stack" for layer in plot.layers):
        raise ConfigError(f"plot '{plot_id}' has variants but no stack layer")

    # the stack's panels move to the view select, as the lines' panels are the labels
    layers = tuple(replace(layer, draw="line") if layer.draw == "stack" else layer for layer in plot.layers)
    lines = replace(plot, layers=layers, panels="label", select_view=plot.select_view or plot.panels)
    stacked = replace(plot, id=f"{plot.id}_stacked", title=f"{plot.title} (Stacked)") if "lines" in variants else plot

    return [lines if variant == "lines" else stacked for variant in variants]


def _plot(plot_id: str, section: str, raw: dict) -> Plot:
    layer_keys = {f.name for f in fields(Layer)} | {"total"}
    unknown = set(raw) - _PLOT_KEYS - layer_keys

    if unknown:
        raise ConfigError(f"plot '{plot_id}' has unknown keys: {', '.join(sorted(unknown))}")

    layers = raw.get("layers") or [{k: v for k, v in raw.items() if k in layer_keys}]

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


def _layer(plot_id: str, raw: dict) -> Layer:
    values = dict(raw)
    total = values.pop("total", False)
    unknown = set(values) - {f.name for f in fields(Layer)}

    if unknown:
        raise ConfigError(f"a layer of plot '{plot_id}' has unknown keys: {', '.join(sorted(unknown))}")

    if total and "split_by" in values:
        raise ConfigError(f"a layer of plot '{plot_id}' has both total and split_by")

    series = values["series"]
    values["series"] = tuple(_series(plot_id, s) for s in ([series] if isinstance(series, str) else series))

    if total:
        values["split_by"] = None

    return Layer(**values)


def _series(plot_id: str, series: str) -> tuple[str, str]:
    """A series "kind.attribute" as (kind, attribute)."""
    kind, _, attribute = series.partition(".")

    if not kind or not attribute:
        raise ConfigError(f"plot '{plot_id}': series '{series}' is not 'kind.attribute'")

    return kind, attribute
