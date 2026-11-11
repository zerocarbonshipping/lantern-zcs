"""Every plot of plots.yaml has data in Navigate's results, and draws in every view and panel, alone and with others."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from lantern.session import Session

if TYPE_CHECKING:
    from pathlib import Path


def test_every_plot_has_data(single: Path) -> None:
    """Every plot has data in a run that touches every attribute, so a misspelled or renamed attribute shows."""
    session = Session([single])
    missing = [entry["id"] for entry in session.catalogue(session.runs) if not entry["available"]]

    assert not missing


@pytest.mark.parametrize("files", ["single", "compiled", "both"])
def test_every_plot_draws(files: str, single: Path, compiled: Path, subtests: pytest.Subtests) -> None:
    """Every plot with data draws, as a figure and as CSV, in every view and panel, of one run or several together."""
    session = Session({"single": [single], "compiled": [compiled], "both": [single, compiled]}[files])
    runs = session.runs

    for entry in session.catalogue(runs):
        if not entry["available"]:
            continue

        for view in [value for value, _ in entry["views"]] or [None]:
            panels = [value for value, _ in session.panels(entry["id"], runs, view)]

            for panel in [None, *panels]:
                with subtests.test(plot=entry["id"], view=view, panel=panel):
                    figure = json.loads(session.figure(entry["id"], runs, view, panel))
                    csv = session.table(entry["id"], runs, view, panel)[0]

                    assert figure["data"]
                    assert len(csv.splitlines()) > 1


def test_compiled_runs(compiled: Path) -> None:
    """A compiled file lists its runs by file and name, without the runs that summarise others."""
    assert Session([compiled]).runs == ["study/a", "study/b"]


def test_band(compiled: Path) -> None:
    """A run with a summary gets its band, low to high, and its median; a run without one only its line."""
    session = Session([compiled])
    both = json.loads(session.figure("main_emission_absolute", ["study/a", "study/b"], None))
    traces = {trace["name"]: trace for trace in both["data"]}
    a, b = (json.loads(session.figure("main_emission_absolute", [run], None))["data"] for run in ("study/a", "study/b"))

    assert [trace["fill"] for trace in a if "fill" in trace] == ["tonexty"]
    assert not [trace for trace in b if "fill" in trace]
    assert traces["a low"]["y"] == pytest.approx([0.8 * y for y in traces["a median"]["y"]])
    assert traces["a high"]["y"] == pytest.approx([1.2 * y for y in traces["a median"]["y"]])


def test_plot_without_data(single: Path) -> None:
    """A plot of no runs, or of a view the runs lack, draws empty instead of failing."""
    session = Session([single])

    assert json.loads(session.figure("main_emission_absolute", [], None))["data"] == []
    assert json.loads(session.figure("main_fuel_consumed", session.runs, "no_such_view"))["data"] == []
    assert session.table("main_emission_absolute", [], None)[0].count("\n") == 1
