# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Open Navigate results files, single runs or compiled ensembles, lazily and resolve plot specs into tidy lines.

A file is never read whole: one scan of a run reads the rows of the plotted series only, with text as categories,
and each plot reduces them to their median and band.
"""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from lantern.config import Layer, Plot

LABELS = ("kind", "node", "attribute", "key1", "key2")
# a line of a prepared plot: its view ("" for a plot without views), panel, layer and label; it has a point per date
LINE = ("view", "panel", "layer", "label")
BAND = (0.05, 0.95)
_POINT = (*LINE, "date")
_TEXT = ("view", "panel", "label")
_YEAR = 365.25  # days, the calendar year Navigate counts steps in

_VALUE = pl.col("value")


class ResultsFileError(ValueError):
    """A file that is not a readable Navigate results file."""


@dataclass(frozen=True)
class ResultsFile:
    """An opened results file: its name, the unit of each attribute, its table, read lazily, the samples of each run,
    the length of each time step in years and the heating values, GJ/t, of its fuels and of each plant's fuel."""

    name: str
    units: dict[str, str]
    scan: pl.LazyFrame
    samples: pl.DataFrame
    steps: pl.DataFrame
    heating_values: dict[str, float]
    plant_fuel: dict[str, str]
    compiled: bool

    @property
    def runs(self) -> dict[str, int]:
        """The number of samples of each run."""
        return dict(self.samples.group_by("run").len().sort("run").rows())

    def scan_run(self, run: str) -> pl.LazyFrame:
        """The rows of a run, read lazily: labels, date, value and sample; the row groups of other runs are skipped."""
        if not self.compiled:
            return self.scan.select(*LABELS, "date", "value", sample=pl.lit(self.name))

        return self.scan.filter(pl.col("run") == run.removeprefix(f"{self.name}/")).select(*LABELS, "date", "value", "sample")


def open_file(source: Path | bytes, name: str) -> ResultsFile:
    """Open a results file: one run, or, compiled, several runs named '<file>/<run>' of one or more samples."""
    try:
        meta = json.loads(pl.read_parquet_metadata(_source(source))["navigate"])
        scan = pl.scan_parquet(_source(source))
        compiled = "sample" in scan.collect_schema().names()

        if compiled:
            samples = scan.select(run=pl.lit(f"{name}/") + pl.col("run"), sample="sample").unique().collect(engine="streaming")

        else:
            samples = pl.DataFrame({"run": [name], "sample": [name]})

        dates = scan.select(pl.col("date").unique()).collect(engine="streaming").sort("date")

    except (KeyError, ValueError, pl.exceptions.PolarsError) as e:
        raise ResultsFileError(f"'{name}' is not a Navigate results file") from e

    # the first step counts as a year, as in the run
    steps = dates.with_columns(step=(pl.col("date").diff().dt.total_days() / _YEAR).fill_null(1.0))
    constants = meta.get("constants", {})

    return ResultsFile(
        name, meta.get("units", {}), scan, samples.sort("run", "sample"), steps,
        constants.get("lower_heating_value", {}), meta.get("plant_fuel", {}), compiled,
    )


def _source(source: Path | bytes) -> Path | io.BytesIO:
    return io.BytesIO(source) if isinstance(source, bytes) else source


def results_files(paths: list[Path]) -> list[tuple[Path, str]]:
    """Results files with names: a file is named after itself, a file in a folder by its path in the folder."""
    found = []

    for path in paths:
        if path.is_dir():
            found.extend((f, f.relative_to(path).with_suffix("").as_posix()) for f in _folder_files(path))

        elif path.is_file():
            found.append((path, path.stem))

        else:
            raise FileNotFoundError(f"no such file or folder: '{path}'")

    return found


def _folder_files(folder: Path) -> list[Path]:
    """The .parquet files in a folder and below, but not below a compiled file, which holds the samples there."""
    files = sorted(folder.glob("*.parquet"))

    if any(_is_compiled(f) for f in files):
        if any(sub.is_dir() for sub in folder.iterdir()):
            print(f"Skipping the subfolders of {folder}: it holds a compiled results file", file=sys.stderr)

        return files

    for sub in sorted(p for p in folder.iterdir() if p.is_dir()):
        files.extend(_folder_files(sub))

    return files


def _is_compiled(path: Path) -> bool:
    """Whether a file is a compiled results file, from the sample list Horizon writes into its metadata."""
    try:
        return "samples" in json.loads(pl.read_parquet_metadata(path)["navigate"])

    except (KeyError, ValueError, pl.exceptions.PolarsError):
        return False


@dataclass(frozen=True)
class Run:
    """The rows of a run of each plotted series, (kind, attribute), in memory with text as categories, an empty frame
    of their columns, the run's samples and its file."""

    name: str
    rows: dict[tuple[str, str], pl.DataFrame]
    empty: pl.DataFrame
    samples: pl.Series
    file: ResultsFile


def read_run(file: ResultsFile, run: str, plots: tuple[Plot, ...]) -> Run:
    """Read the rows of a run of every series the plots name, in one scan of the file."""
    series = sorted({s for plot in plots for layer in plot.layers for s in layer.series})
    # an enum of the run's samples is the smallest type to join on
    samples = file.samples.filter(pl.col("run") == run).get_column("sample")
    sample = pl.Enum(samples)
    rows = file.scan_run(run).filter(_wanted(series))
    # a value that is not finite, such as an unbounded constraint or NaN, cannot be drawn, so it is missing
    rows = rows.with_columns(
        pl.col(*LABELS).cast(pl.Categorical), pl.col("sample").cast(sample), value=pl.when(_VALUE.is_finite()).then(_VALUE),
    ).collect(engine="streaming")

    # split once, as filtering the run's rows for each layer would take longer than preparing it
    return Run(run, rows.partition_by("kind", "attribute", as_dict=True), rows.clear(), samples.cast(sample), file)


def prepare(plot: Plot, run: Run, representative: str | None) -> pl.DataFrame:
    """Resolve every layer of a plot of a run, in each of its views, into lines: run, view, panel, layer, label, date,
    low, value, high, representative.

    value is the median over the run's samples, low and high the band around it and representative the
    value of the representative sample, if given; a stack has all three the representative's value, as
    medians do not add up. A run of one sample has all its value.
    """
    # a run without a representative gets the column null; comparing with None gives that too, but polars warns
    pick = pl.col("sample") == representative if representative is not None else pl.lit(False)
    layers = []

    for index, layer in enumerate(plot.layers):
        values = _samples(index, layer, plot, run).group_by(_POINT).agg(
            low=_VALUE.quantile(BAND[0], "linear"), value=_VALUE.median(), high=_VALUE.quantile(BAND[1], "linear"),
            representative=_VALUE.filter(pick).first(),
        )

        if layer.draw == "stack" and representative is not None:
            values = values.with_columns(low="representative", value="representative", high="representative")

        layers.append(values)

    lines = pl.concat(layers).with_columns(pl.col(*_TEXT).cast(pl.String)).sort(_POINT)

    return lines.select(pl.lit(run.name).alias("run"), pl.all())


def per_sample(plot: Plot, run: Run) -> pl.DataFrame:
    """Every layer of a plot of a run, as lines per sample: view, panel, layer, label, date, sample, value."""
    return pl.concat([_samples(index, layer, plot, run) for index, layer in enumerate(plot.layers)])


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


def _samples(index: int, layer: Layer, plot: Plot, run: Run) -> pl.DataFrame:
    rows = _select(run, layer.series)

    if layer.per_energy:
        # a value whose fuel the file gives no heating value for cannot be converted
        rows = rows.with_columns(heating_value=_heating_value(run.file)).filter(pl.col("heating_value").is_not_null())
        rows = rows.with_columns(value=_VALUE / pl.col("heating_value"))

    if plot.panels == "label":
        panel = _label(layer)

    else:
        panel = pl.col(plot.panels).fill_null("") if plot.panels else pl.lit("")

    view = pl.col(plot.views).fill_null("") if plot.views else pl.lit("")
    rows = rows.with_columns(label=_label(layer), panel=panel, view=view, layer=pl.lit(index, pl.Int32))
    # a constant is text, not a category, so every text key is cast for the layers to concatenate
    rows = rows.with_columns(pl.col(*_TEXT).cast(pl.Categorical))

    # one value per sample; a date with no value stays missing, so the line breaks there
    values = rows.group_by(*_POINT, "sample").agg(pl.when(_VALUE.count() > 0).then(_VALUE.sum() * layer.scale))

    # a sample without the series has it negligible, as the results file leaves such series out; usually none lacks it
    short = values.group_by(_POINT).len().filter(pl.col("len") < run.samples.len())

    if not short.is_empty():
        missing = short.join(run.samples.to_frame(), how="cross").join(values, on=[*_POINT, "sample"], how="anti")
        values = pl.concat([values, missing.select(*_POINT, "sample", value=pl.lit(0.0, values.schema["value"]))])

    return _accumulate(values, run.file.steps) if layer.cumulative else values


def _accumulate(values: pl.DataFrame, steps: pl.DataFrame) -> pl.DataFrame:
    """Sum each line over the time steps up to and including each date, as Navigate's report does.

    A value is a rate over the step ending at its date; a missing value adds nothing.
    """
    return values.join(steps, on="date").sort("date").select(
        *_POINT, "sample", value=(_VALUE.fill_null(0.0) * pl.col("step")).cum_sum().over(*LINE, "sample")
    )


def _heating_value(file: ResultsFile) -> pl.Expr:
    """The heating value, GJ/t, of the fuel a row is about: a plant's own fuel, else the fuel in key1, if the file gives it.

    A compiled file carries no constants, so its rows have none.
    """
    plant_fuel = pl.col("node").replace_strict(file.plant_fuel, default=None, return_dtype=pl.String)
    fuel = pl.when(pl.col("kind") == "plant").then(plant_fuel).otherwise(pl.col("key1"))

    return fuel.replace_strict(file.heating_values, default=None, return_dtype=pl.Float32)


def _label(layer: Layer) -> pl.Expr:
    if layer.by is None:
        return pl.lit(layer.name) if layer.name else pl.col("attribute")

    return pl.col(layer.by).fill_null(layer.name or "total")
