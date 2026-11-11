"""
Open Navigate results files lazily and resolve plot specs into tidy lines.

A file holds a single run, or, compiled, several runs. It is never read whole: one scan of a run reads the rows of the
plotted series only, with text as categories, and each plot reduces them to a line per label. A Horizon study's file
holds, per scenario, the representative run and its summary over the samples as runs of their own, which its metadata
names under summaries; those give the scenario's lines their median and band.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import polars as pl

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

    from lantern.config import Layer, Plot

LABELS = ("kind", "node", "attribute", "key1", "key2")
COLUMNS = (*LABELS, "date", "value")
# a line of a prepared plot: its run, view ("" for a plot without views), panel, layer and label; it has a point per
# date
LINE = ("run", "view", "panel", "layer", "label")
_POINT = (*LINE, "date")
_TEXT = ("view", "panel", "label")
# the columns of the summary of a run over the samples it represents, as a Horizon file's metadata names them
SUMMARY = ("median", "low", "high")
# the columns of prepared lines, as prepare() returns them: the value, and the summary where the run has one
LINES = {
    "run": pl.String,
    "view": pl.String,
    "panel": pl.String,
    "layer": pl.Int32,
    "label": pl.String,
    "date": pl.Date,
    "value": pl.Float64,
    **dict.fromkeys(SUMMARY, pl.Float64),
}
_YEAR = 365.25  # days, the calendar year Navigate counts steps in

_VALUE = pl.col("value")


class ResultsFileError(Exception):
    """A file that is not a readable Navigate results file."""


@dataclass(frozen=True)
class ResultsFile:
    """
    An opened results file, its table read lazily.

    It carries its name, the unit of each attribute, its runs, each run's summary runs by column, the length of each
    time step in years and the heating values, GJ/t, of its fuels and of each plant's fuel.
    """

    name: str
    units: dict[str, str]
    scan: pl.LazyFrame
    runs: list[str]
    summaries: dict[str, dict[str, str]]
    steps: pl.DataFrame
    heating_values: dict[str, float]
    plant_fuel: dict[str, str]
    compiled: bool

    def scan_runs(self, runs: list[str]) -> pl.LazyFrame:
        """Scan the rows of the runs lazily: run, labels, date and value; the row groups of other runs are skipped."""
        if not self.compiled:
            return self.scan.select(run_id(self.name, compiled=False), *COLUMNS)

        names = [run.removeprefix(f"{self.name}/") for run in runs]

        return self.scan.filter(pl.col("run").is_in(names)).select(run_id(self.name, compiled=True), *COLUMNS)


def open_file(source: Path | bytes, name: str) -> ResultsFile:
    """
    Open a results file: one run, or, compiled, several runs named '<file>/<run>'.

    A Horizon file's summary runs are listed under the runs they summarise, not as runs.
    """
    try:
        meta = json.loads(pl.read_parquet_metadata(_source(source))["navigate"])
        scan = pl.scan_parquet(_source(source))
        schema = scan.collect_schema()
        missing = [column for column in COLUMNS if column not in schema]

        if missing:
            raise ResultsFileError(f"'{name}' lacks the columns {', '.join(missing)}")

        compiled = "run" in schema
        runs = _runs(scan, name) if compiled else [name]
        summaries = _summaries(meta, name)
        runs = [run for run in runs if run not in {r for summary in summaries.values() for r in summary.values()}]
        dates = scan.select(pl.col("date").unique()).collect(engine="streaming").sort("date")

    except (KeyError, ValueError, pl.exceptions.PolarsError) as e:
        raise ResultsFileError(f"'{name}' is not a Navigate results file") from e

    # the first step counts as a year, as in the run
    steps = dates.with_columns(step=(pl.col("date").diff().dt.total_days() / _YEAR).fill_null(1.0))
    constants = meta.get("constants", {})

    return ResultsFile(
        name,
        meta.get("units", {}),
        scan,
        runs,
        summaries,
        steps,
        constants.get("lower_heating_value", {}),
        meta.get("plant_fuel", {}),
        compiled,
    )


def _source(source: Path | bytes) -> Path | io.BytesIO:
    """Return a file's path, or its content as a file to read."""
    return io.BytesIO(source) if isinstance(source, bytes) else source


def run_id(name: str, compiled: bool) -> pl.Expr:
    """Return the run column of a file's rows: the file's name, or '<file>/<run>' in a compiled file."""
    return (pl.lit(f"{name}/") + pl.col("run") if compiled else pl.lit(name)).alias("run")


def _runs(scan: pl.LazyFrame, name: str) -> list[str]:
    """List the runs of a compiled file, named '<file>/<run>', in name order."""
    runs = scan.select(run_id(name, compiled=True)).unique().collect(engine="streaming")

    return runs.get_column("run").sort().to_list()


def _summaries(meta: dict[str, Any], name: str) -> dict[str, dict[str, str]]:
    """Each run's summary runs, by column, as a Horizon file's metadata names them, all named '<file>/<run>'."""
    return {
        f"{name}/{run}": {column: f"{name}/{other}" for column, other in summary.items()}
        for run, summary in meta.get("summaries", {}).items()
    }


def results_files(paths: list[Path]) -> list[tuple[Path, str]]:
    """Results files with names: a file is named after itself, a file in a folder by its path in the folder."""
    found: list[tuple[Path, str]] = []

    for path in paths:
        if path.is_dir():
            found.extend((f, f.relative_to(path).with_suffix("").as_posix()) for f in sorted(path.rglob("*.parquet")))

        elif path.is_file():
            found.append((path, path.stem))

        else:
            raise FileNotFoundError(f"no such file or folder: '{path}'")

    return found


@dataclass(frozen=True)
class Runs:
    """
    The rows of some runs and of their summary runs, of each plotted series, (kind, attribute), in memory.

    Text is held as categories. It also carries an empty frame of their columns, each run's summary runs by column and
    the runs' file.
    """

    rows: dict[tuple[str, str], pl.DataFrame]
    empty: pl.DataFrame
    summaries: dict[str, dict[str, str]]
    file: ResultsFile


def read_runs(file: ResultsFile, runs: Sequence[str], plots: tuple[Plot, ...]) -> Runs:
    """Read the rows of the runs and their summary runs, of every series the plots name or divide by, in one scan."""
    summaries = {run: file.summaries.get(run, {}) for run in runs}
    names = [*runs, *(other for summary in summaries.values() for other in summary.values())]
    series = sorted({s for plot in plots for layer in plot.layers for s in (*layer.series, layer.per) if s})
    rows = file.scan_runs(names).filter(_wanted(series))
    # a value that is not finite, such as an unbounded constraint or NaN, cannot be drawn, so it is missing; a file
    # holds its values as 32- or 64-bit floats, and as 64-bit the lines of several files concatenate
    rows = rows.with_columns(
        pl.col("run", *LABELS).cast(pl.Categorical),
        value=pl.when(_VALUE.is_finite()).then(_VALUE).cast(pl.Float64),
    ).collect(engine="streaming")

    # split once, as filtering the rows for each layer would take longer than preparing it
    return Runs(rows.partition_by("kind", "attribute", as_dict=True), rows.clear(), summaries, file)


def prepare(plot: Plot, runs: Runs) -> pl.DataFrame:
    """
    Resolve every layer of a plot of the runs, in each of its views, into lines, the columns of LINES.

    A value is the sum of the series that share a label, missing where none has one, and the median, low and high are
    the values of a run's summary runs, missing without one. All runs are resolved together, as a query takes about as
    long for one run as for many.
    """
    lines = _prepare(plot, runs)
    summary_runs = [other for summary in runs.summaries.values() for other in summary.values()]

    if not summary_runs:
        return lines.with_columns([pl.lit(None, pl.Float64).alias(column) for column in SUMMARY])

    # a summary run's line becomes a column of the line of the run it summarises
    summarised = lines.filter(pl.col("run").is_in(summary_runs))
    lines = lines.filter(~pl.col("run").is_in(summary_runs))

    for column in SUMMARY:
        owners = {other: run for run, summary in runs.summaries.items() if (other := summary.get(column))}
        values = summarised.filter(pl.col("run").is_in(list(owners))).with_columns(pl.col("run").replace_strict(owners))
        values = values.select(*_POINT, pl.col("value").alias(column))
        lines = lines.join(values, on=_POINT, how="left", maintain_order="left")

    return lines


def _prepare(plot: Plot, runs: Runs) -> pl.DataFrame:
    layers = [_lines(index, layer, plot, runs) for index, layer in enumerate(plot.layers)]

    return pl.concat(layers).with_columns(pl.col("run", *_TEXT).cast(pl.String)).sort(_POINT)


def unit(plot: Plot, units: dict[str, str]) -> str:
    """Return the y unit of a plot: its own, else that of the first attribute it names."""
    if plot.unit is not None:
        return plot.unit

    _, attribute = plot.layers[0].series[0]

    return units.get(attribute, "")


def _select(runs: Runs, series: tuple[tuple[str, str], ...]) -> pl.DataFrame:
    """Rows of the runs of any of the series, each (kind, attribute) over every node of the kind."""
    frames = [runs.rows[s] for s in series if s in runs.rows]

    return pl.concat(frames) if frames else runs.empty


def _wanted(series: Iterable[tuple[str, str]]) -> pl.Expr:
    return pl.any_horizontal([(pl.col("kind") == kind) & (pl.col("attribute") == attribute) for kind, attribute in series])


def _lines(index: int, layer: Layer, plot: Plot, runs: Runs) -> pl.DataFrame:
    rows = _select(runs, layer.series)

    if layer.per_gj:
        # a value whose fuel the file gives no heating value for cannot be converted
        rows = rows.with_columns(heating_value=_heating_value(runs.file)).filter(pl.col("heating_value").is_not_null())
        rows = rows.with_columns(value=_VALUE / pl.col("heating_value"))

    if layer.per:
        rows = _per(rows, layer.per, layer, plot, runs)

    view = pl.col(plot.select_view).fill_null("") if plot.select_view else pl.lit("")
    rows = rows.with_columns(label=_label(layer), panel=_panel(plot, layer), view=view, layer=pl.lit(index, pl.Int32))
    # a constant is text, not a category, so every text key is cast for the layers to concatenate
    rows = rows.with_columns(pl.col(*_TEXT).cast(pl.Categorical))

    # one value per date, summed over the series that share a label; a date with no value stays missing, so the line
    # breaks there
    values = rows.group_by(*_POINT).agg(pl.when(_VALUE.count() > 0).then(_VALUE.sum() * layer.scale))

    return _accumulate(values, runs.file.steps) if layer.cumulative else values


def _accumulate(values: pl.DataFrame, steps: pl.DataFrame) -> pl.DataFrame:
    """
    Sum each line over the time steps up to and including each date, as Navigate's report does.

    A value is a rate over the step ending at its date; a missing value adds nothing.
    """
    return (
        values.join(steps, on="date")
        .sort("date")
        .select(*_POINT, value=(_VALUE.fill_null(0.0) * pl.col("step")).cum_sum().over(*LINE))
    )


def _per(rows: pl.DataFrame, per: tuple[str, str], layer: Layer, plot: Plot, runs: Runs) -> pl.DataFrame:
    """
    Divide the rows by the layer's per series, (kind, attribute), of their run at their date.

    The divisor is summed over all its rows but for the columns the lines, panels or views are split by: node by node
    within its own kind, and key by key where it has the key. The divisor of every row of a line is then the same, so a
    line is the ratio of the sums, and the lines of a stack split otherwise add up to the total's. A row without a
    divisor at its date, or with zero, is left out.
    """
    kind, _ = per
    divisor = runs.rows.get(per, runs.empty)
    split = {plot.panels, plot.select_view, layer.split_by}
    on = [
        column
        for column in ("node", "key1", "key2")
        if column in split
        and (all(k == kind for k, _ in layer.series) if column == "node" else divisor.get_column(column).count() > 0)
    ]
    divisor = divisor.group_by("run", "date", *on).agg(per=_VALUE.sum()).filter(pl.col("per") != 0)

    return rows.join(divisor, on=["run", "date", *on]).with_columns(value=_VALUE / pl.col("per"))


def _heating_value(file: ResultsFile) -> pl.Expr:
    """
    Return the heating value, GJ/t, of a row's fuel: a plant's own fuel, else the fuel in key1, if the file gives it.

    A compiled file carries no constants, so its rows have none.
    """
    plant_fuel = pl.col("node").replace_strict(file.plant_fuel, default=None, return_dtype=pl.String)
    fuel = pl.when(pl.col("kind") == "plant").then(plant_fuel).otherwise(pl.col("key1"))

    return fuel.replace_strict(file.heating_values, default=None, return_dtype=pl.Float32)


def _panel(plot: Plot, layer: Layer) -> pl.Expr:
    if plot.panels == "label":
        return _label(layer)

    return pl.col(plot.panels).fill_null("") if plot.panels else pl.lit("")


def _label(layer: Layer) -> pl.Expr:
    if layer.split_by is None:
        return pl.lit(layer.label) if layer.label else pl.col("attribute")

    return pl.col(layer.split_by).fill_null(layer.label or "total")
