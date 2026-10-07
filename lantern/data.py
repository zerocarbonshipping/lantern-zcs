# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Read Navigate results files and resolve plot specs into tidy series."""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from functools import reduce
from pathlib import Path

import polars as pl

from lantern.config import Layer, Plot

SCHEMA_VERSION = 1
LABELS = ("kind", "node", "attribute", "key1", "key2")
KEYS = ("run", "panel", "layer", "label", "date")
SERIES = ("run", "panel", "layer", "label")
YEAR = 365.25
EMPTY = 1e-9

# years each step spans; the first step counts as one year
_STEP = (pl.col("date").diff().dt.total_days() / YEAR).fill_null(1.0).over(SERIES, order_by="date")
_VALUE = pl.col("value")
_TRANSFORMS = {
    "per_year": _VALUE / _STEP,
    "cumulative": (_VALUE.fill_nan(0.0) * _STEP).cum_sum().over(SERIES, order_by="date"),
    "negate": -_VALUE,
}


class ResultsFileError(ValueError):
    """A file that is not a readable Navigate results file."""


@dataclass(frozen=True)
class Run:
    """One run: its name, the unit of each attribute and its long results table."""

    name: str
    units: dict[str, str]
    frame: pl.DataFrame


def read_run(data: bytes, name: str) -> Run:
    """Read the content of a results file."""
    try:
        meta = json.loads(pl.read_parquet_metadata(io.BytesIO(data))["navigate"])
        frame = pl.read_parquet(io.BytesIO(data), columns=[*LABELS, "date", "value"])

    except (KeyError, ValueError, pl.exceptions.PolarsError) as e:
        raise ResultsFileError(f"'{name}' is not a Navigate results file") from e

    if meta.get("schema_version") != SCHEMA_VERSION:
        raise ResultsFileError(f"'{name}' has results schema {meta.get('schema_version')}, not {SCHEMA_VERSION}")

    # an infinite value is an unbounded limit: there is nothing to draw
    frame = frame.with_columns(
        *(pl.col(c).cast(pl.String) for c in LABELS),
        value=pl.when(_VALUE.is_infinite()).then(float("nan")).otherwise(_VALUE),
        run=pl.lit(name),
    )

    return Run(name, meta.get("units", {}), frame)


def results_files(paths: list[Path]) -> list[tuple[Path, str]]:
    """Results files with run names: a file is named after itself, a file in a folder by its path in the folder."""
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
    """Resolve every layer of a plot into series: run, panel, layer, label, date, value."""
    if plot.split and node is not None:
        frame = frame.filter(pl.col(plot.split) == node)

    layers = [_layer(index, layer, plot, frame) for index, layer in enumerate(plot.layers)]

    return pl.concat(layers).sort(*KEYS)


def unit(plot: Plot, units: dict[str, str]) -> str:
    """The y unit of a plot: its own, else that of the first attribute it names."""
    if plot.unit is not None:
        return plot.unit

    layer = plot.layers[0]
    attribute = (layer.series[0].split("/") + ["*"] * 3)[2]
    result = units.get(attribute, "")

    return result.removesuffix("/year") if "cumulative" in layer.transforms else result


def has_data(plot: Plot, frame: pl.DataFrame) -> bool:
    """Whether any layer selects a value worth drawing."""
    return any(not _informative(frame, layer).is_empty() for layer in plot.layers)


def split_nodes(plot: Plot, frame: pl.DataFrame) -> list[str]:
    """The views a split plot offers, sorted."""
    if not plot.split:
        return []

    rows = pl.concat([_informative(frame, layer) for layer in plot.layers])

    return sorted(v for v in rows.get_column(plot.split).unique().to_list() if v)


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


def _informative(frame: pl.DataFrame, layer: Layer) -> pl.DataFrame:
    return select(frame, layer.series).filter(_VALUE.fill_nan(None).abs() > EMPTY)


def _layer(index: int, layer: Layer, plot: Plot, frame: pl.DataFrame) -> pl.DataFrame:
    panel = pl.col(plot.facet).fill_null("") if plot.facet else pl.lit("")
    rows = select(frame, layer.series).with_columns(label=_label(layer), panel=panel, layer=pl.lit(index, pl.Int32))

    series = rows.group_by(KEYS).agg(_VALUE.sum())

    for name in layer.transforms:
        scale = name.removeprefix("scale:")
        series = series.with_columns(value=_VALUE * float(scale) if scale != name else _TRANSFORMS[name])

    # drop series that are zero or missing throughout
    magnitude = _VALUE.fill_nan(None).abs().sum().over("layer", "panel", "label")

    return series.filter(magnitude > EMPTY).select(*KEYS, "value")


def _label(layer: Layer) -> pl.Expr:
    if layer.label is None:
        return pl.lit(layer.name) if layer.name else pl.col("attribute")

    return pl.col(layer.label).fill_null(layer.name or "total")
