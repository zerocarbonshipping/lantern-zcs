"""The command line: list the plots, write the rows to CSV and plots to HTML, and stop with a message on a bad input."""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

import polars as pl
import pytest

from lantern.__main__ import main
from lantern.config import load_config

if TYPE_CHECKING:
    from pathlib import Path


def lantern(monkeypatch: pytest.MonkeyPatch, *args: str | Path) -> int:
    """Run lantern with the arguments, in the test's working folder."""
    monkeypatch.setattr(sys, "argv", ["lantern", *map(str, args)])

    return main()


def test_list(single: Path, compiled: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """--list prints the runs and the id of every plot with data."""
    assert lantern(monkeypatch, single, compiled, "--list") == 0

    out = capsys.readouterr().out
    listed = [line.split()[0] for line in out.partition("Plots with data:\n")[2].splitlines() if not line.startswith(" " * 3)]

    assert "  attribute_coverage\n  study/a\n  study/b\n" in out
    assert listed == [plot.id for plot in load_config().plots]


def test_data(single: Path, compiled: Path, working_folder: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--data writes every row of the files, the compiled file's summary runs too, to one CSV."""
    assert lantern(monkeypatch, single, compiled, "--data") == 0

    rows = pl.read_csv(working_folder / "data.csv")

    assert rows.columns == ["run", "kind", "node", "attribute", "key1", "key2", "date", "value"]
    assert rows.get_column("run").unique().sort().to_list() == [
        "attribute_coverage",
        *(f"study/{run}" for run in sorted(["a", "b", "a_median", "a_p05", "a_p95"])),
    ]


def test_plot(single: Path, compiled: Path, working_folder: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--plot writes a plot of each run, of runs together, and one panel of it, as HTML pages."""
    args = ["--plot", "main_emission_absolute", "--plot", "main_fuel_consumed[study/a,study/b][hfo]"]

    assert lantern(monkeypatch, single, compiled, *args) == 0

    written = sorted(path.relative_to(working_folder / "plots").as_posix() for path in working_folder.rglob("*.html"))

    assert written == [
        "a/main_emission_absolute.html",
        "attribute_coverage/main_emission_absolute.html",
        "b/main_emission_absolute.html",
        "main_fuel_consumed/a+b_hfo.html",
    ]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--plot", "no_such_plot"], "no plot no_such_plot"),
        (["--plot", "main_emission_absolute[no_such_run]"], "no run no_such_run"),
    ],
)
def test_unknown(
    args: list[str], message: str, single: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unknown plot or run stops with a message."""
    assert lantern(monkeypatch, single, *args) == 1
    assert message in capsys.readouterr().err


@pytest.mark.parametrize("content", [b"not parquet", b""], ids=["text", "empty"])
def test_not_results(
    content: bytes, working_folder: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file that is not a results file stops with a message."""
    path = working_folder / "other.parquet"
    path.write_bytes(content)

    assert lantern(monkeypatch, path, "--list") == 1
    assert "'other' is not a Navigate results file" in capsys.readouterr().err


def test_parquet_without_columns(
    working_folder: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A Parquet file with Navigate's metadata but not its columns stops with a message naming them."""
    path = working_folder / "other.parquet"
    pl.DataFrame({"value": [1.0]}).write_parquet(path, metadata={"navigate": "{}"})

    assert lantern(monkeypatch, path, "--list") == 1
    assert "'other' lacks the columns kind, node, attribute, key1, key2, date" in capsys.readouterr().err


def test_missing_path(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """A path that does not exist stops with a message."""
    assert lantern(monkeypatch, "missing.parquet", "--list") == 1
    assert "no such file or folder" in capsys.readouterr().err


def test_entry_point(single: Path, plots_yaml: Path, working_folder: Path) -> None:
    """The installed lantern command runs, reading plots.yaml from the folder it is started in."""
    shutil.copy(plots_yaml, working_folder)
    command = shutil.which("lantern")

    assert command, "lantern is not installed"

    done = subprocess.run([command, str(single), "--list"], capture_output=True, text=True, check=False)

    assert done.returncode == 0, done.stderr
    assert "main_emission_absolute" in done.stdout
