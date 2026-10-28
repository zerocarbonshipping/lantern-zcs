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


# a plot to write: its id, the runs drawn together or None for each run alone, and a panel or None for all panels
type Spec = tuple[str, list[str] | None, str | None]


class ExportError(Exception):
    """An export that cannot be written."""


def plots(session: Session, folder: Path, specs: list[Spec]) -> None:
    """Write plots as PNG, as the viewer opens them: a plot with a node select in its first view.

    A spec, a plot id, runs and a panel as listing() names them, writes that plot of each loaded run when runs is None,
    else one figure of the runs drawn together, as the viewer compares them, and only the panel if one is given, as
    the viewer enlarges it; the paths written are printed. A run's own plot is <folder>/<run>/<plot id>.png, one of
    several runs <folder>/<plot id>/<run>+<run>.png, a run named as in its file, and a panel's "_<panel>" before ".png".
    """
    every_run = session.runs
    # a / in a name would make a run a folder
    names = {run: name.replace("/", "_") for run, name in session.short_names(every_run).items()}
    plot_ids = [plot.id for plot in session.config.plots]
    available = {run: {entry["id"] for entry in session.catalogue([run]) if entry["available"]} for run in every_run}
    figures: list[tuple[tuple[str, ...], str, str | None]] = []
    skipped = []

    # every figure first, so the progress bar knows how many there are and a misspelled id stops before any is drawn
    for plot_id, runs, panel in specs:
        _known("plot", [plot_id], plot_ids)
        panel = _panel(session, plot_id, every_run, panel)

        if runs is None:
            figures += [((run,), plot_id, panel) for run in every_run if plot_id in available[run]]
            skipped += [f"{plot_id} in {run}" for run in every_run if plot_id not in available[run]]
            continue

        _known("run", runs, every_run)
        runs = tuple(dict.fromkeys(runs))

        if any(plot_id in available[run] for run in runs):
            figures.append((runs, plot_id, panel))
        else:
            skipped.append(f"{plot_id} in {'+'.join(runs)}")

    paths = []

    for runs, plot_id, panel in tqdm(figures, desc="Plotting", unit="plot", colour="green", dynamic_ncols=True,
                                     disable=None):
        # a run without the panel gets the whole plot, as the viewer does
        if panel is not None and panel not in [value for value, _ in session.panels(plot_id, list(runs))]:
            skipped.append(f"panel {panel} of {plot_id} in {'+'.join(runs)}")
            continue

        path = _path(folder, [names[run] for run in runs], plot_id, panel)
        path.parent.mkdir(parents=True, exist_ok=True)
        figure = session.draw(plot_id, list(runs), None, panel)
        figure.update_layout(width=_WIDTH, height=_HEIGHT)
        _write_png(figure, path)
        paths.append(path)

    print(f"Wrote {len(paths)} plots to {folder}", flush=True)
    print("\n".join(str(path) for path in paths), flush=True)

    if skipped:
        print(f"No data, so not written: {', '.join(skipped)}", flush=True)


def listing(session: Session) -> str:
    """The loaded runs and the plots with data in any of them, with the panels of their first view, as --plot takes
    them."""
    runs = session.runs
    entries = [entry for entry in session.catalogue(runs) if entry["available"]]
    width = max((len(entry["id"]) for entry in entries), default=0)
    lines = ["Runs:", *(f"  {run}" for run in runs), "Plots with data:"]

    for entry in entries:
        panels = [value for value, _ in session.panels(entry["id"], runs)]
        lines.append(f"  {entry['id']:<{width}}  {entry['section']}: {entry['title']}")

        if len(panels) > 1:
            lines.append(f"  {'':<{width}}  panels: {', '.join(panels)}")

    return "\n".join(lines) + "\n"


def _known(kind: str, names: list[str], known: list[str]) -> None:
    """Stop at a name that is not known."""
    if unknown := [name for name in dict.fromkeys(names) if name not in known]:
        raise ExportError(f"no {kind} {', '.join(unknown)} in the loaded files; `lantern PATH --list` lists them")


def _panel(session: Session, plot_id: str, runs: list[str], panel: str | None) -> str | None:
    """A panel of a plot by its value or its display name, as --list and the page show them."""
    if panel is None:
        return None

    panels = session.panels(plot_id, runs)
    found = [value for value, title in panels if panel in (value, title)]

    if not found:
        raise ExportError(f"no panel {panel} in {plot_id}; its panels are {', '.join(value for value, _ in panels)}")

    return found[0]


def _path(folder: Path, names: list[str], plot_id: str, panel: str | None) -> Path:
    """Where a figure goes: a run's own in its folder, one of several runs in the plot's, named after them; a panel's
    is named after the panel too."""
    suffix = f"_{panel}" if panel else ""

    if len(names) == 1:
        return folder / names[0] / f"{plot_id}{suffix}.png"

    return folder / plot_id / ("+".join(names) + f"{suffix}.png")


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
