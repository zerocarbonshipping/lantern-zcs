# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Choose the representative sample of an ensemble run: the one that stays closest to the median.

At every date, each series of a plot with a weight ranks the run's samples as percentiles from 0 to 100,
which makes series of any unit comparable. A sample's distance in a series is its mean squared distance
from the 50th percentile over the dates; its score is that averaged over the plot's series, so a plot's
weight is split evenly across them, and then weighted over the plots. The lowest score wins, a tie going
to the first sample by name.
"""

from __future__ import annotations

from collections.abc import Iterable

import polars as pl

from lantern import data
from lantern.config import Plot

_SERIES = [key for key in data.KEYS if key != "date"]


def choose(plots: Iterable[Plot], frame: pl.DataFrame) -> str | None:
    """The representative sample of one run, or None for a run of one sample or without weighted series."""
    if frame.get_column("sample").n_unique() < 2:
        return None

    scores = [_distances(plot, frame).with_columns(weight=pl.lit(plot.weight)) for plot in plots if plot.weight > 0]
    scores = pl.concat(scores).drop_nulls("distance") if scores else None

    if scores is None or scores.is_empty():
        return None

    weighted = (pl.col("distance") * pl.col("weight")).sum() / pl.col("weight").sum()

    return scores.group_by("sample").agg(score=weighted).sort("score", "sample").get_column("sample").first()


def _distances(plot: Plot, frame: pl.DataFrame) -> pl.DataFrame:
    """Each sample's mean squared distance from the median percentile, averaged over the plot's series."""
    values = data.per_sample(plot, frame)
    # the percentile of each sample's value among those of the date, ties sharing the mean rank; one value is the median
    count = pl.col("value").count().over(data.KEYS)
    rank = pl.col("value").rank("average").over(data.KEYS)
    percentile = pl.when(count > 1).then((rank - 1) / (count - 1) * 100).otherwise(50.0)

    return (
        values.with_columns(squared=(percentile - 50.0) ** 2)
        .group_by(*_SERIES, "sample").agg(pl.col("squared").mean())
        .group_by("sample").agg(distance=pl.col("squared").mean())
    )
