# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Load a results file: read each run once, choose its representative sample and prepare every plot of all runs."""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from lantern import data, representative
from lantern.config import Plot


@dataclass(frozen=True)
class Results:
    """A results file, loaded or loading: its name, units and runs, the representative sample of each run read, the
    prepared lines of every plot prepared with data, by plot id, and whether all are; the file itself is not kept."""

    name: str
    units: dict[str, str]
    runs: dict[str, int]
    compiled: bool
    representatives: dict[str, str | None]
    plots: dict[str, pl.DataFrame]
    complete: bool


def load(
    source: Path | bytes, name: str, plots: tuple[Plot, ...], progress: Callable[[str, int, int], None],
) -> Iterator[Results]:
    """Load a results file, yielding it once opened, again as each plot is prepared and at last complete; progress is
    told the step it starts and how many of how many steps are done."""
    progress("opening", 0, 0)
    file = data.open_file(source, name)
    names = file.runs
    total, done = 2 * len(names) + len(plots), itertools.count()
    runs, representatives, prepared = {}, {}, {}

    def results(complete: bool = False) -> Results:
        return Results(name, file.units, names, file.compiled, dict(representatives), dict(prepared), complete)

    yield results()

    # every run is read first, so the plots are ready in their order, each for all runs; the runs' rows stay in
    # memory until the last plot is prepared
    for run_name in names:
        short = run_name.removeprefix(f"{name}/")
        progress(f"{short}: reading", next(done), total)
        runs[run_name] = data.read_run(file, run_name, plots)
        progress(f"{short}: representative sample", next(done), total)
        representatives[run_name] = representative.choose(plots, runs[run_name])

    for plot in plots:
        progress(plot.title, next(done), total)
        lines = [data.prepare(plot, run, representatives[run_name]) for run_name, run in runs.items()]
        lines = [frame for frame in lines if not frame.is_empty()]

        if lines:
            prepared[plot.id] = pl.concat(lines)
            yield results()

    print(f"Loaded {name}: {len(names)} run(s), {len(prepared)} of {len(plots)} plots with data", flush=True)

    yield results(complete=True)
