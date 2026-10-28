# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Open Navigate results files, single runs or compiled files of several runs, lazily and resolve plot specs into tidy
lines.

A file is never read whole: one scan of a run reads the rows of the plotted series only, with text as categories,
and each plot reduces them to a line per label. A Horizon study's file holds, per scenario, the representative run
and its summary over the samples as runs of their own, which its metadata names under summaries; those give the
scenario's lines their median and band.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from lantern.config import Layer, Plot

LABELS = ("kind", "node", "attribute", "key1", "key2")
COLUMNS = (*LABELS, "date", "value")
# a line of a prepared plot: its view ("" for a plot without views), panel, layer and label; it has a point per date
LINE = ("view", "panel", "layer", "label")
_POINT = (*LINE, "date")
_TEXT = ("view", "panel", "label")
# the columns of the summary of a run over the samples it represents, as a Horizon file's metadata names them
SUMMARY = ("median", "low", "high")
# the columns of prepared lines, as prepare() returns them: the value, and the summary where the run has one
LINES = {
    "run": pl.String, "view": pl.String, "panel": pl.String, "layer": pl.Int32, "label": pl.String, "date": pl.Date,
    "value": pl.Float64, **{column: pl.Float64 for column in SUMMARY},
}
_YEAR = 365.25  # days, the calendar year Navigate counts steps in

_VALUE = pl.col("value")


class ResultsFileError(ValueError):
    """A file that is not a readable Navigate results file."""


@dataclass(frozen=True)
class ResultsFile:
    """An opened results file: its name, the unit of each attribute, its table, read lazily, its runs, each run's
    summary runs by column, the length of each time step in years and the heating values, GJ/t, of its fuels and of
    each plant's fuel."""

    name: str
    units: dict[str, str]
    scan: pl.LazyFrame
    runs: list[str]
    summaries: dict[str, dict[str, str]]
    steps: pl.DataFrame
    heating_values: dict[str, float]
    plant_fuel: dict[str, str]
    compiled: bool

    def scan_run(self, run: str) -> pl.LazyFrame:
        """The rows of a run, read lazily: labels, date and value; the row groups of other runs are skipped."""
        if not self.compiled:
            return self.scan.select(*COLUMNS)

        return self.scan.filter(pl.col("run") == run.removeprefix(f"{self.name}/")).select(*COLUMNS)


def open_file(source: Path | bytes, name: str) -> ResultsFile:
    """Open a results file: one run, or, compiled, several runs named '<file>/<run>'; a Horizon file's summary runs
    are listed under the runs they summarise, not as runs."""
    try:
        meta = json.loads(pl.read_parquet_metadata(_source(source))["navigate"])
        schema = pl.read_parquet_schema(_source(source))
        missing = [column for column in COLUMNS if column not in schema]

        if missing:
            raise ResultsFileError(f"'{name}' lacks the columns {', '.join(missing)}")

        scan = pl.scan_parquet(_source(source))
        compiled = "run" in schema
        runs = _runs(scan, name) if compiled else [name]
        summaries = _summaries(meta, name)
        runs = [run for run in runs if run not in {r for summary in summaries.values() for r in summary.values()}]
        dates = scan.select(pl.col("date").unique()).collect(engine="streaming").sort("date")

    # a ResultsFileError is a ValueError, so it passes before the others are wrapped as one
    except ResultsFileError:
        raise

    except (KeyError, ValueError, pl.exceptions.PolarsError) as e:
        raise ResultsFileError(f"'{name}' is not a Navigate results file") from e

    # the first step counts as a year, as in the run
    steps = dates.with_columns(step=(pl.col("date").diff().dt.total_days() / _YEAR).fill_null(1.0))
    constants = meta.get("constants", {})

    return ResultsFile(
        name, meta.get("units", {}), scan, runs, summaries, steps, constants.get("lower_heating_value", {}),
        meta.get("plant_fuel", {}), compiled,
    )


def _source(source: Path | bytes) -> Path | io.BytesIO:
    return io.BytesIO(source) if isinstance(source, bytes) else source


def _runs(scan: pl.LazyFrame, name: str) -> list[str]:
    """The runs of a compiled file, named '<file>/<run>', in name order."""
    runs = scan.select(run=pl.lit(f"{name}/") + pl.col("run")).unique().collect(engine="streaming")

    return runs.get_column("run").sort().to_list()


def _summaries(meta: dict, name: str) -> dict[str, dict[str, str]]:
    """Each run's summary runs, by column, as a Horizon file's metadata names them, all named '<file>/<run>'."""
    return {
        f"{name}/{run}": {column: f"{name}/{other}" for column, other in summary.items()}
        for run, summary in meta.get("summaries", {}).items()
    }


def results_files(paths: list[Path]) -> list[tuple[Path, str]]:
    """Results files with names: a file is named after itself, a file in a folder by its path in the folder."""
    found = []

    for path in paths:
        if path.is_dir():
            found.extend((f, f.relative_to(path).with_suffix("").as_posix()) for f in sorted(path.rglob("*.parquet")))

        elif path.is_file():
            found.append((path, path.stem))

        else:
            raise FileNotFoundError(f"no such file or folder: '{path}'")

    return found


@dataclass(frozen=True)
class Run:
    """The rows of a run of each plotted series, (kind, attribute), in memory with text as categories, an empty frame
    of their columns and the run's file."""

    name: str
    rows: dict[tuple[str, str], pl.DataFrame]
    empty: pl.DataFrame
    file: ResultsFile


def read_run(file: ResultsFile, run: str, plots: tuple[Plot, ...]) -> Run:
    """Read the rows of a run of every series the plots name, in one scan of the file."""
    series = sorted({s for plot in plots for layer in plot.layers for s in layer.series})
    rows = file.scan_run(run).filter(_wanted(series))
    # a value that is not finite, such as an unbounded constraint or NaN, cannot be drawn, so it is missing; a file
    # holds its values as 32- or 64-bit floats, and as 64-bit the lines of several files concatenate
    rows = rows.with_columns(
        pl.col(*LABELS).cast(pl.Categorical), value=pl.when(_VALUE.is_finite()).then(_VALUE).cast(pl.Float64),
    ).collect(engine="streaming")

    # split once, as filtering the run's rows for each layer would take longer than preparing it
    return Run(run, rows.partition_by("kind", "attribute", as_dict=True), rows.clear(), file)


def prepare(plot: Plot, run: Run, summary: dict[str, Run] | None = None) -> pl.DataFrame:
    """Resolve every layer of a plot of a run, in each of its views, into lines, the columns of LINES: a value is the
    sum of the series that share a label, missing where none has one, and the median, low and high are the values of
    the run's summary runs, missing without one."""
    lines = _prepare(plot, run)

    for column in SUMMARY:
        other = (summary or {}).get(column)

        if other is None or lines.is_empty():
            lines = lines.with_columns(pl.lit(None, pl.Float64).alias(column))
            continue

        values = _prepare(plot, other).select(*_POINT, pl.col("value").alias(column))
        lines = lines.join(values, on=_POINT, how="left")

    return lines


def _prepare(plot: Plot, run: Run) -> pl.DataFrame:
    layers = [_lines(index, layer, plot, run) for index, layer in enumerate(plot.layers)]
    lines = pl.concat(layers).with_columns(pl.col(*_TEXT).cast(pl.String)).sort(_POINT)

    return lines.select(pl.lit(run.name).alias("run"), pl.all())


def unit(plot: Plot, units: dict[str, str]) -> str:
    """The y unit of a plot: its own, else that of the first attribute it names."""
    if plot.unit is not None:
        return plot.unit

    _, attribute = plot.layers[0].series[0]

    return units.get(attribute, "")


def _select(run: Run, series: tuple[tuple[str, str], ...]) -> pl.DataFrame:
    """Rows of a run of any of the series, each (kind, attribute) over every node of the kind."""
    frames = [run.rows[s] for s in series if s in run.rows]

    return pl.concat(frames) if frames else run.empty


def _wanted(series: Iterable[tuple[str, str]]) -> pl.Expr:
    return pl.any_horizontal([(pl.col("kind") == kind) & (pl.col("attribute") == attribute) for kind, attribute in series])


def _lines(index: int, layer: Layer, plot: Plot, run: Run) -> pl.DataFrame:
    rows = _select(run, layer.series)

    if layer.per_gj:
        # a value whose fuel the file gives no heating value for cannot be converted
        rows = rows.with_columns(heating_value=_heating_value(run.file)).filter(pl.col("heating_value").is_not_null())
        rows = rows.with_columns(value=_VALUE / pl.col("heating_value"))

    if plot.panels == "label":
        panel = _label(layer)

    else:
        panel = pl.col(plot.panels).fill_null("") if plot.panels else pl.lit("")

    view = pl.col(plot.select_view).fill_null("") if plot.select_view else pl.lit("")
    rows = rows.with_columns(label=_label(layer), panel=panel, view=view, layer=pl.lit(index, pl.Int32))
    # a constant is text, not a category, so every text key is cast for the layers to concatenate
    rows = rows.with_columns(pl.col(*_TEXT).cast(pl.Categorical))

    # one value per date, summed over the series that share a label; a date with no value stays missing, so the line
    # breaks there
    values = rows.group_by(*_POINT).agg(pl.when(_VALUE.count() > 0).then(_VALUE.sum() * layer.scale))

    return _accumulate(values, run.file.steps) if layer.cumulative else values


def _accumulate(values: pl.DataFrame, steps: pl.DataFrame) -> pl.DataFrame:
    """Sum each line over the time steps up to and including each date, as Navigate's report does.

    A value is a rate over the step ending at its date; a missing value adds nothing.
    """
    return values.join(steps, on="date").sort("date").select(
        *_POINT, value=(_VALUE.fill_null(0.0) * pl.col("step")).cum_sum().over(*LINE)
    )


def _heating_value(file: ResultsFile) -> pl.Expr:
    """The heating value, GJ/t, of the fuel a row is about: a plant's own fuel, else the fuel in key1, if the file gives it.

    A compiled file carries no constants, so its rows have none.
    """
    plant_fuel = pl.col("node").replace_strict(file.plant_fuel, default=None, return_dtype=pl.String)
    fuel = pl.when(pl.col("kind") == "plant").then(plant_fuel).otherwise(pl.col("key1"))

    return fuel.replace_strict(file.heating_values, default=None, return_dtype=pl.Float32)


def _label(layer: Layer) -> pl.Expr:
    if layer.split_by is None:
        return pl.lit(layer.label) if layer.label else pl.col("attribute")

    return pl.col(layer.split_by).fill_null(layer.label or "total")
