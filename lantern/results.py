# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Load a results file: read each run once and prepare every plot of it."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from lantern import data
from lantern.config import Plot


@dataclass(frozen=True)
class Results:
    """A loaded results file: its name, units and runs, and the prepared lines of every plot with data, by plot id;
    the file itself is not kept."""

    name: str
    units: dict[str, str]
    runs: list[str]
    compiled: bool
    plots: dict[str, pl.DataFrame]


def load(source: Path | bytes, name: str, plots: tuple[Plot, ...]) -> Results:
    """Load a results file: open it, read each run and prepare every plot of it, keeping the plots with data."""
    file = data.open_file(source, name)
    lines: dict[str, list[pl.DataFrame]] = {plot.id: [] for plot in plots}

    # a run's rows stay in memory only while its plots are prepared
    for run_name in file.runs:
        run = data.read_run(file, run_name, plots)

        for plot in plots:
            frame = data.prepare(plot, run)

            if not frame.is_empty():
                lines[plot.id].append(frame)

    prepared = {plot_id: pl.concat(frames) for plot_id, frames in lines.items() if frames}
    print(f"Loaded {name}: {len(file.runs)} run(s), {len(prepared)} of {len(plots)} plots with data", flush=True)

    return Results(name, file.units, file.runs, file.compiled, prepared)
