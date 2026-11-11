"""Load a results file: read each run once and prepare every plot of it."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import TYPE_CHECKING

import polars as pl

from lantern import data

if TYPE_CHECKING:
    from pathlib import Path

    from lantern.config import Plot

# runs read and prepared together; a query takes about as long for one run as for many
_BATCH = 20


@dataclass(frozen=True)
class Results:
    """
    A loaded results file: its name, units and runs, and the prepared lines of every plot with data, by plot id.

    The file itself is not kept.
    """

    name: str
    units: dict[str, str]
    runs: list[str]
    compiled: bool
    plots: dict[str, pl.DataFrame]


def load(source: Path | bytes, name: str, plots: tuple[Plot, ...]) -> Results:
    """Load a results file: open it, read each run and prepare every plot of it, keeping the plots with data."""
    file = data.open_file(source, name)
    lines: dict[str, list[pl.DataFrame]] = {plot.id: [] for plot in plots}

    # the runs go in batches, each read in one scan and prepared in one query per plot; a batch's rows, with its summary
    # runs', stay in memory only while its plots are prepared, which bounds the memory a study of many runs takes
    for batch in itertools.batched(file.runs, _BATCH):
        runs = data.read_runs(file, batch, plots)

        for plot in plots:
            frame = data.prepare(plot, runs)

            if not frame.is_empty():
                lines[plot.id].append(frame)

    prepared = {plot_id: pl.concat(frames) for plot_id, frames in lines.items() if frames}
    print(f"Loaded {name}: {len(file.runs)} run(s), {len(prepared)} of {len(plots)} plots with data", flush=True)

    return Results(name, file.units, file.runs, file.compiled, prepared)
