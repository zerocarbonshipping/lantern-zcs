# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Write what the viewer shows to files instead of serving it: a plot as PNG, or the rows of the results files as one
CSV."""

from __future__ import annotations

from pathlib import Path

import polars as pl
from tqdm import tqdm

from lantern import data
from lantern.server import Session

# an exported PNG is 1080p, 1920 by 1080 pixels: laid out at 1280 by 720 px and drawn at 1.5 pixels per px, so its
# text and lines are half again as large as the viewer shows them on such a screen
_SCALE = 1.5
_WIDTH = round(1920 / _SCALE)
_HEIGHT = round(1080 / _SCALE)


class ExportError(Exception):
    """An export that cannot be written."""


def plots(session: Session, folder: Path, specs: list[tuple[str, list[str] | None]]) -> None:
    """Write plots as PNG, as the viewer opens them: a plot with a node select in its first view.

    A spec, a plot id and runs as listing() names them, writes that plot of each loaded run when runs is None, else
    one figure of the runs drawn together, as the viewer compares them; the paths written are printed. A run's own
    plot is <folder>/<run>/<plot id>.png, one of several runs <folder>/<plot id>/<run>+<run>.png, a run named as in
    its file.
    """
    every_run = _runs(session)
    names = _file_names(session)
    plot_ids = [plot.id for plot in session.config.plots]
    available = {run: {entry["id"] for entry in session.catalogue([run]) if entry["available"]} for run in every_run}
    figures: list[tuple[tuple[str, ...], str]] = []
    skipped = []

    # every figure first, so the progress bar knows how many there are and a misspelled id stops before any is drawn
    for plot_id, runs in specs:
        _known("plot", [plot_id], plot_ids)

        if runs is None:
            figures += [((run,), plot_id) for run in every_run if plot_id in available[run]]
            skipped += [f"{plot_id} in {run}" for run in every_run if plot_id not in available[run]]
            continue

        _known("run", runs, every_run)
        runs = tuple(dict.fromkeys(runs))

        if any(plot_id in available[run] for run in runs):
            figures.append((runs, plot_id))
        else:
            skipped.append(f"{plot_id} in {'+'.join(runs)}")

    paths = []

    for runs, plot_id in tqdm(figures, desc="Plotting", unit="plot", colour="green", dynamic_ncols=True, disable=None):
        path = _path(folder, [names[run] for run in runs], plot_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        figure = session.draw(plot_id, list(runs), None)
        figure.update_layout(width=_WIDTH, height=_HEIGHT)
        _write_png(figure, path)
        paths.append(path)

    print(f"Wrote {len(paths)} plots to {folder}", flush=True)
    print("\n".join(str(path) for path in paths), flush=True)

    if skipped:
        print(f"No data, so not written: {', '.join(skipped)}", flush=True)


def listing(session: Session) -> str:
    """The loaded runs and the plots with data in any of them, by the ids --plot takes."""
    runs = _runs(session)
    entries = [entry for entry in session.catalogue(runs) if entry["available"]]
    width = max((len(entry["id"]) for entry in entries), default=0)
    lines = [
        "Runs:", *(f"  {run}" for run in runs),
        "Plots with data:", *(f"  {entry['id']:<{width}}  {entry['section']}: {entry['title']}" for entry in entries),
    ]

    return "\n".join(lines) + "\n"


def _runs(session: Session) -> list[str]:
    return [run for file in session.files.values() for run in file.runs]


def _known(kind: str, names: list[str], known: list[str]) -> None:
    """Stop at a name that is not known."""
    if unknown := [name for name in dict.fromkeys(names) if name not in known]:
        raise ExportError(f"no {kind} {', '.join(unknown)} in the loaded files; `lantern PATH --list` lists them")


def _file_names(session: Session) -> dict[str, str]:
    """Each run's name in a path: its name within its compiled file, the full id where two files share it, a / as _ so
    a run is one folder."""
    short = {run: run.removeprefix(f"{f.name}/") for f in session.files.values() for run in f.runs}
    names = list(short.values())

    return {run: (name if names.count(name) == 1 else run).replace("/", "_") for run, name in short.items()}


def _path(folder: Path, names: list[str], plot_id: str) -> Path:
    """Where a figure goes: a run's own in its folder, one of several runs in the plot's, named after them."""
    if len(names) == 1:
        return folder / names[0] / f"{plot_id}.png"

    return folder / plot_id / ("+".join(names) + ".png")


def rows(sources: list[Path], path: Path) -> None:
    """Write the rows of the results files at the sources, every series and date, as one CSV: run, kind, node,
    attribute, key1, key2, date, value."""
    frames = []

    for file, name in data.results_files(sources):
        scan = pl.scan_parquet(file)
        schema = scan.collect_schema()

        if missing := set(data.COLUMNS) - set(schema):
            raise data.ResultsFileError(f"'{name}' lacks the columns {', '.join(sorted(missing))}")

        run = pl.concat_str([pl.lit(f"{name}/"), pl.col("run")]) if "run" in schema else pl.lit(name)
        labels = [pl.col(c).cast(pl.String) for c in data.LABELS]
        frames.append(scan.select(run.alias("run"), *labels, "date", pl.col("value").cast(pl.Float64)))

    if not frames:
        raise data.ResultsFileError("no results files to write")

    pl.concat(frames).sink_csv(path)
    print(f"Wrote the rows of {len(frames)} file(s) to {path}", flush=True)


def _write_png(figure, path: Path) -> None:
    try:
        figure.write_image(path, format="png", scale=_SCALE)

    except Exception as e:  # noqa: BLE001 - kaleido and its browser fail in many ways, each with its own message
        raise ExportError(
            f"cannot write {path}: PNG export needs kaleido and Chrome; pip install 'lantern-zcs[export]' and run "
            f"plotly_get_chrome once\n{e}"
        ) from e
