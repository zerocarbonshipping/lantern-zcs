"""The loaded results files and what is drawn from each of their runs, for the viewer and the exports."""

from __future__ import annotations

import threading
from collections import Counter
from typing import TYPE_CHECKING, Any, TypedDict

import polars as pl

from lantern import data, figures, results
from lantern.config import Config, Plot, load_config

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import plotly.graph_objects as go

    from lantern.results import Results


class PlotEntry(TypedDict):
    """A plot of the catalogue: whether any of the runs has data for it, and its views, [value, title]."""

    id: str
    title: str
    section: str
    available: bool
    views: list[list[str]]


class Session:
    """
    The results files at the sources and those added on the page, and what is drawn from each of their runs.

    Requests hold the lock, as the session is not thread-safe; a file loads within the request that adds or refreshes
    it, which holds up the other requests until it is loaded.
    """

    config: Config
    files: dict[str, Results]

    def __init__(self, sources: list[Path]) -> None:
        """Read the configuration and load the results files at the sources."""
        self.sources = sources
        # the contents of the files added on the page, to load again on refresh
        self.uploads: dict[str, bytes] = {}
        self.lock = threading.Lock()
        self._cache: dict[tuple[str | None, ...], Any] = {}
        self.refresh()

    def add(self, content: bytes, name: str) -> None:
        """Load a results file added on the page, in place of a loaded one of the same name."""
        self.files[name] = results.load(content, name, self.config.plots)
        self.uploads[name] = content
        self._cache.clear()

    def refresh(self) -> None:
        """
        Read the configuration again and reload the results files at the sources and those added on the page.

        The files at the sources are read as they are on disk now and replace those loaded before; nothing changes if
        any is unreadable.
        """
        config = load_config()
        found = {name: path for path, name in data.results_files(self.sources)} | self.uploads
        files = {name: results.load(source, name, config.plots) for name, source in found.items()}
        self.config, self.files = config, files
        self._cache.clear()

    def remove(self, name: str) -> None:
        """Unload a results file."""
        self.files.pop(name, None)
        self.uploads.pop(name, None)
        self._cache.clear()

    @property
    def runs(self) -> list[str]:
        """Every loaded run, in the order of the files."""
        return [run for f in self.files.values() for run in f.runs]

    def short_names(self, runs: list[str]) -> dict[str, str]:
        """Each run's name within its file, in the order given; the full id where two files have a run of that name."""
        short = {run: run.removeprefix(f"{f.name}/") for f in self.files.values() for run in f.runs}

        return _distinct({run: short[run] for run in runs})

    def state(self) -> dict[str, object]:
        """Return the files with their runs, and each run's display name, for the page."""
        files = [{"name": f.name, "compiled": f.compiled, "runs": f.runs} for f in self.files.values()]

        return {"files": files, "names": self._names(self.runs)}

    def catalogue(self, runs: list[str]) -> list[PlotEntry]:
        """List the plots, with whether any of the runs has data for each and its views, [value, title]."""

        def compute() -> list[PlotEntry]:
            entries: list[PlotEntry] = []

            for plot in self.config.plots:
                lines = self._lines(plot, runs)
                views = [[view, self.config.labels.get(view, view)] for view in _views(lines)]
                entries.append(
                    {
                        "id": plot.id,
                        "title": plot.title,
                        "section": plot.section,
                        "available": not lines.is_empty(),
                        "views": views,
                    }
                )

            return entries

        return self._cached(("catalogue", *runs), compute)

    def figure(self, plot_id: str, runs: list[str], view: str | None, panel: str | None = None) -> str:
        """
        Draw one figure of the runs as Plotly JSON, or one panel of it enlarged.

        A plot with views shows its first by default.
        """

        def compute() -> str:
            figure: str = self.draw(plot_id, runs, view, panel).to_json()

            return figure

        return self._cached((plot_id, *runs, view, panel), compute)

    def draw(self, plot_id: str, runs: list[str], view: str | None, panel: str | None = None) -> go.Figure:
        """One figure of the runs, or one panel of it enlarged; a plot with views shows its first by default."""
        plot = self.config.plot(plot_id)
        lines, _ = self._view(plot, runs, view)

        return figures.build(plot, lines, data.unit(plot, self._units()), self.config, self._names(runs), panel)

    def table(self, plot_id: str, runs: list[str], view: str | None, panel: str | None = None) -> tuple[str, str]:
        """Return the lines of a figure as CSV, with a file name: the plot's id, view and unit."""
        plot = self.config.plot(plot_id)
        lines, view = self._view(plot, runs, view)
        unit = data.unit(plot, self._units()).replace("/", " per ")
        parts = (plot_id, self.config.labels.get(view, view) if view else "", f"({unit})" if unit else "")
        name = " ".join(filter(None, parts))

        return figures.table(lines, self.config, self._names(runs), panel), f"{name}.csv"

    def panels(self, plot_id: str, runs: list[str], view: str | None = None) -> list[list[str]]:
        """List the panels of a figure, [value, title], in the order drawn."""
        lines, _ = self._view(self.config.plot(plot_id), runs, view)

        return [[p, self.config.labels.get(p, p)] for p in figures.panels_of(lines, self.config)]

    def _lines(self, plot: Plot, runs: list[str]) -> pl.DataFrame:
        """Return the prepared lines of a plot of the runs, over all its views."""
        lines = [f.plots[plot.id] for f in self.files.values() if plot.id in f.plots and not set(f.runs).isdisjoint(runs)]

        return pl.concat(lines).filter(pl.col("run").is_in(runs)) if lines else pl.DataFrame(schema=data.LINES)

    def _view(self, plot: Plot, runs: list[str], view: str | None) -> tuple[pl.DataFrame, str | None]:
        """Return the lines of a plot of the runs in one view, the given one or else the first, and that view."""
        lines = self._lines(plot, runs)
        view = view or next(iter(_views(lines)), None)

        return lines.filter(pl.col("view") == (view or "")), view

    def _names(self, runs: list[str]) -> dict[str, str]:
        """
        Return each run's display name, as plots.yaml names it, else its name within its file.

        plots.yaml names a run by its name within its file; the full id stands in where two display names are alike.
        """
        return _distinct({run: self.config.run_names.get(name, name) for run, name in self.short_names(runs).items()})

    def _units(self) -> dict[str, str]:
        return {k: v for f in self.files.values() for k, v in f.units.items()}

    def _cached[T](self, key: tuple[str | None, ...], compute: Callable[[], T]) -> T:
        if key not in self._cache:
            self._cache[key] = compute()

        value: T = self._cache[key]

        return value


def _views(lines: pl.DataFrame) -> list[str]:
    """List the views of a plot's lines, in name order; a plot without select_view has none."""
    return sorted(view for view in lines.get_column("view").unique().to_list() if view)


def _distinct(names: dict[str, str]) -> dict[str, str]:
    """Return the names, with the key itself in place of a name two keys share."""
    counts = Counter(names.values())

    return {key: name if counts[name] == 1 else key for key, name in names.items()}
