"""plots.yaml: the repository's reads, and a mistake in one stops with a message that says where, not a traceback."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from lantern import config
from lantern.config import ConfigError, load_config

if TYPE_CHECKING:
    from pathlib import Path

PLOT = "main:\n  emission:\n    title: WTW emissions\n    series: global.total_equivalent_wtw\n"


def test_repository_plots() -> None:
    """The repository's plots.yaml reads, with plot ids made of section and key."""
    plots = load_config().plots

    assert plots[0].id == "main_emission_absolute"
    assert len({plot.id for plot in plots}) == len(plots)


def test_plot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The smallest plot reads: a title and a series."""
    path = tmp_path / "plots.yaml"
    path.write_text(PLOT)
    monkeypatch.setattr(config, "PLOTS_FILES", (path,))

    (plot,) = load_config().plots

    assert (plot.id, plot.section, plot.layers[0].series) == ("main_emission", "Main", (("global", "total_equivalent_wtw"),))


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("- main\n- fleet\n", "must map keys to entries"),
        ("main: [emission]\n", "section 'main' must map plot keys to plots"),
        ("main:\n  emission: WTW emissions\n", "plot 'main_emission' must map keys to values"),
        ("main:\n  emission:\n    series: global.total_equivalent_wtw\n", "plot 'main_emission' has no title"),
        ("main:\n  emission:\n    title: WTW emissions\n", "plot 'main_emission' has no series"),
        (PLOT + "    layers: [global.consumed_energy]\n", "layers must list layers, each mapping keys to values"),
        (PLOT + "    colour: red\n", "plot 'main_emission' has unknown keys: colour"),
        (PLOT + "    y_axis: log\n", "y_axis must be zero or fit, not 'log'"),
        (PLOT.replace("global.total_equivalent_wtw", "total_equivalent_wtw"), "is not 'kind.attribute'"),
        (PLOT + "    label: no\n", "line 5: 'no' reads as bool; quote it"),
        (PLOT + "customize_runs:\n  base: {name: Base, color: not_a_colour}\n", "'not_a_colour' is neither a colour name"),
        (PLOT + "theme:\n  swatches: {accent: teal}\n", "the swatches accent are not hex values"),
        (PLOT + "    cumulative: true\n    per: global.transport_work\n", "has both cumulative and per"),
    ],
    ids=[
        "not a mapping",
        "section not a mapping",
        "plot not a mapping",
        "no title",
        "no series",
        "layer not a mapping",
        "unknown key",
        "y_axis",
        "series without kind",
        "unquoted no",
        "colour",
        "swatch",
        "cumulative per",
    ],
)
def test_mistake(text: str, message: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A mistake in plots.yaml stops with a message that names it."""
    path = tmp_path / "plots.yaml"
    path.write_text(text)
    monkeypatch.setattr(config, "PLOTS_FILES", (path,))

    with pytest.raises(ConfigError, match=re.escape(message)):
        load_config()


def test_no_plots_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a plots.yaml, Lantern says where it looked."""
    monkeypatch.setattr(config, "PLOTS_FILES", (tmp_path / "plots.yaml",))

    with pytest.raises(ConfigError, match=re.escape("no plots.yaml in the working folder or the home folder")):
        load_config()
