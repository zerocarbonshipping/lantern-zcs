# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Read Navigate results files, single runs or compiled ensembles, and resolve plot specs into tidy series."""

from __future__ import annotations

import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from lantern.config import Layer, Plot

LABELS = ("kind", "node", "attribute", "key1", "key2")
KEYS = ("panel", "layer", "label", "date")
BAND = (0.05, 0.95)
_YEAR = 365.25  # days, the calendar year Navigate counts steps in

_VALUE = pl.col("value")


class ResultsFileError(ValueError):
    """A file that is not a readable Navigate results file."""


@dataclass(frozen=True)
class ResultsFile:
    """A loaded results file: its name, the unit of each attribute, its long table and the samples of each run."""

    name: str
    units: dict[str, str]
    frame: pl.DataFrame
    runs: dict[str, int]
    compiled: bool


def read_file(data: bytes, name: str) -> ResultsFile:
    """Read a results file: one run, or, compiled, several runs named '<file>/<run>' of one or more samples."""
    try:
        meta = json.loads(pl.read_parquet_metadata(io.BytesIO(data))["navigate"])
        frame = pl.read_parquet(io.BytesIO(data))
        compiled = "sample" in frame.columns
        frame = frame.select(
            *LABELS, "date", "value",
            run=pl.lit(f"{name}/") + pl.col("run") if compiled else pl.lit(name),
            sample=pl.col("sample") if compiled else pl.lit(name),
            heating_value=_heating_value(meta),
        )
        runs = dict(frame.group_by("run").agg(pl.col("sample").n_unique()).sort("run").rows())

    except (KeyError, ValueError, pl.exceptions.PolarsError) as e:
        raise ResultsFileError(f"'{name}' is not a Navigate results file") from e

    return ResultsFile(name, meta.get("units", {}), frame, runs, compiled)


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


def prepare(plot: Plot, frame: pl.DataFrame, node: str | None = None, representative: str | None = None) -> pl.DataFrame:
    """Resolve every layer of a plot of one run into series: panel, layer, label, date, low, value, high, representative.

    value is the median over the run's samples, low and high the band around it and representative the
    value of the representative sample, if given; a stack has all three the representative's value, as
    medians do not add up. A run of one sample has all its value.
    """
    samples = frame.select(pl.col("sample").unique())

    if plot.views and node is not None:
        frame = frame.filter(pl.col(plot.views) == node)

    # a run without a representative gets the column null; comparing with None gives that too, but polars warns
    pick = pl.col("sample") == representative if representative is not None else pl.lit(False)
    layers = []

    for index, layer in enumerate(plot.layers):
        values = _samples(index, layer, plot, frame, samples).group_by(KEYS).agg(
            low=_VALUE.quantile(BAND[0], "linear"), value=_VALUE.median(), high=_VALUE.quantile(BAND[1], "linear"),
            representative=_VALUE.filter(pick).first(),
        )

        if layer.draw == "stack" and representative is not None:
            values = values.with_columns(low="representative", value="representative", high="representative")

        layers.append(values)

    return pl.concat(layers).sort(*KEYS)


def per_sample(plot: Plot, frame: pl.DataFrame) -> pl.DataFrame:
    """Every layer of a plot of one run, over all its views, as series per sample: panel, layer, label, date, sample, value."""
    samples = frame.select(pl.col("sample").unique())

    return pl.concat([_samples(index, layer, plot, frame, samples) for index, layer in enumerate(plot.layers)])


def unit(plot: Plot, units: dict[str, str]) -> str:
    """The y unit of a plot: its own, else that of the first attribute it names."""
    if plot.unit is not None:
        return plot.unit

    _, attribute = plot.layers[0].series[0]

    return units.get(attribute, "")


def has_data(plot: Plot, frame: pl.DataFrame) -> bool:
    """Whether any layer selects a series; the file holds only series worth drawing."""
    return not _rows(plot, frame).is_empty()


def split_nodes(plot: Plot, frame: pl.DataFrame) -> list[str]:
    """The views a split plot offers, sorted."""
    if not plot.views:
        return []

    return sorted(v for v in _rows(plot, frame).get_column(plot.views).unique().to_list() if v)


def select(frame: pl.DataFrame, series: tuple[tuple[str, str], ...]) -> pl.DataFrame:
    """Rows of any of the series, each (kind, attribute) over every node of the kind."""
    wanted = pl.DataFrame(list(series), schema=["kind", "attribute"], orient="row")

    return frame.join(wanted, on=["kind", "attribute"], how="semi")


def _rows(plot: Plot, frame: pl.DataFrame) -> pl.DataFrame:
    return select(frame, tuple(s for layer in plot.layers for s in layer.series))


def _samples(index: int, layer: Layer, plot: Plot, frame: pl.DataFrame, samples: pl.DataFrame) -> pl.DataFrame:
    if plot.panels == "label":
        panel = _label(layer)

    else:
        panel = pl.col(plot.panels).fill_null("") if plot.panels else pl.lit("")

    rows = select(frame, layer.series)

    if layer.per_energy:
        # a value whose fuel the file gives no heating value for cannot be converted
        rows = rows.filter(pl.col("heating_value").is_not_null()).with_columns(value=_VALUE / pl.col("heating_value"))

    rows = rows.with_columns(label=_label(layer), panel=panel, layer=pl.lit(index, pl.Int32))

    # one value per sample; a date with no value stays missing, so the line breaks there
    values = rows.group_by(*KEYS, "sample").agg(pl.when(_VALUE.count() > 0).then(_VALUE.sum() * layer.scale))

    # a sample without the series has it negligible, as the results file leaves such series out
    grid = values.select(KEYS).unique().join(samples, how="cross")
    values = grid.join(values.with_columns(present=True), on=[*KEYS, "sample"], how="left")
    values = values.select(*KEYS, "sample", value=pl.when(pl.col("present")).then(_VALUE).otherwise(0.0))

    return _accumulate(values, frame) if layer.cumulative else values


def _accumulate(values: pl.DataFrame, frame: pl.DataFrame) -> pl.DataFrame:
    """Sum each series over the time steps up to and including each date, as Navigate's report does.

    A value is a rate over the step ending at its date, the first step a year long; a missing value adds nothing.
    """
    steps = frame.select(pl.col("date").unique().sort()).with_columns(
        step=(pl.col("date").diff().dt.total_days() / _YEAR).fill_null(1.0)
    )
    series = [key for key in KEYS if key != "date"]

    return values.join(steps, on="date").sort("date").select(
        *KEYS, "sample", value=(_VALUE.fill_null(0.0) * pl.col("step")).cum_sum().over(*series, "sample")
    )


def _heating_value(meta: dict) -> pl.Expr:
    """The heating value, GJ/t, of the fuel a row is about: a plant's own fuel, else the fuel in key1, if the file gives it.

    A compiled file carries no constants, so its rows have none.
    """
    heating_values = meta.get("constants", {}).get("lower_heating_value", {})
    plant_fuel = pl.col("node").replace_strict(meta.get("plant_fuel", {}), default=None, return_dtype=pl.String)
    fuel = pl.when(pl.col("kind") == "plant").then(plant_fuel).otherwise(pl.col("key1"))

    return fuel.replace_strict(heating_values, default=None, return_dtype=pl.Float32)


def _label(layer: Layer) -> pl.Expr:
    if layer.by is None:
        return pl.lit(layer.name) if layer.name else pl.col("attribute")

    return pl.col(layer.by).fill_null(layer.name or "total")
