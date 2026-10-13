# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Read Navigate results files, single runs or compiled ensembles, and resolve plot specs into tidy series."""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from functools import reduce
from pathlib import Path

import polars as pl

from lantern.config import Layer, Plot

LABELS = ("kind", "node", "attribute", "key1", "key2")
KEYS = ("panel", "layer", "label", "date")
BAND = (0.05, 0.95)

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
            found.extend((f, f.relative_to(path).with_suffix("").as_posix()) for f in sorted(path.rglob("*.parquet")))

        elif path.is_file():
            found.append((path, path.stem))

        else:
            raise FileNotFoundError(f"no such file or folder: '{path}'")

    return found


def prepare(plot: Plot, frame: pl.DataFrame, node: str | None = None) -> pl.DataFrame:
    """Resolve every layer of a plot of one run into series: panel, layer, label, date, and low, value, high.

    value is the median over the run's samples and low and high the band around it; a run of one
    sample has all three its value.
    """
    samples = frame.select(pl.col("sample").unique())

    if plot.split and node is not None:
        frame = frame.filter(pl.col(plot.split) == node)

    layers = [_layer(index, layer, plot, frame, samples) for index, layer in enumerate(plot.layers)]

    return pl.concat(layers).sort(*KEYS)


def unit(plot: Plot, units: dict[str, str]) -> str:
    """The y unit of a plot: its own, else that of the first attribute it names."""
    if plot.unit is not None:
        return plot.unit

    layer = plot.layers[0]
    attribute = (layer.series[0].split("/") + ["*"] * 3)[2]

    return units.get(attribute, "")


def has_data(plot: Plot, frame: pl.DataFrame) -> bool:
    """Whether any layer selects a series; the file holds only series worth drawing."""
    return not _rows(plot, frame).is_empty()


def split_nodes(plot: Plot, frame: pl.DataFrame) -> list[str]:
    """The views a split plot offers, sorted."""
    if not plot.split:
        return []

    return sorted(v for v in _rows(plot, frame).get_column(plot.split).unique().to_list() if v)


def select(frame: pl.DataFrame, selectors: tuple[str, ...]) -> pl.DataFrame:
    """Rows any selector matches."""
    return frame.filter(reduce(lambda a, b: a | b, map(_selector, selectors)))


def _selector(selector: str) -> pl.Expr:
    conditions = [_part(column, part) for column, part in zip(LABELS, selector.split("/"), strict=False) if part != "*"]

    return reduce(lambda a, b: a & b, conditions, pl.lit(True))


def _part(column: str, part: str) -> pl.Expr:
    if "*" not in part:
        return pl.col(column).eq(part).fill_null(False)

    pattern = "^" + ".*".join(map(re.escape, part.split("*"))) + "$"

    return pl.col(column).str.contains(pattern).fill_null(False)


def _rows(plot: Plot, frame: pl.DataFrame) -> pl.DataFrame:
    return select(frame, tuple(s for layer in plot.layers for s in layer.series))


def _layer(index: int, layer: Layer, plot: Plot, frame: pl.DataFrame, samples: pl.DataFrame) -> pl.DataFrame:
    if plot.facet == "label":
        panel = _label(layer)

    else:
        panel = pl.col(plot.facet).fill_null("") if plot.facet else pl.lit("")

    rows = select(frame, layer.series).with_columns(label=_label(layer), panel=panel, layer=pl.lit(index, pl.Int32))

    # one value per sample; a date with no value stays missing, so the line breaks there
    values = rows.group_by(*KEYS, "sample").agg(pl.when(_VALUE.count() > 0).then(_VALUE.sum() * layer.scale))

    # a sample without the series has it negligible, as the results file leaves such series out
    grid = values.select(KEYS).unique().join(samples, how="cross")
    values = grid.join(values.with_columns(present=True), on=[*KEYS, "sample"], how="left")
    values = values.with_columns(value=pl.when(pl.col("present")).then(_VALUE).otherwise(0.0))

    return values.group_by(KEYS).agg(
        low=_VALUE.quantile(BAND[0], "linear"), value=_VALUE.median(), high=_VALUE.quantile(BAND[1], "linear"),
    )


def _label(layer: Layer) -> pl.Expr:
    if layer.label is None:
        return pl.lit(layer.name) if layer.name else pl.col("attribute")

    return pl.col(layer.label).fill_null(layer.name or "total")
