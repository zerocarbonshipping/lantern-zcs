# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Serve the page and its JSON API on localhost; the loaded files are the only state, used by one request at a time."""

from __future__ import annotations

import json
import threading
from collections import Counter
from collections.abc import Callable
from functools import cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import plotly.graph_objects as go
import polars as pl
from plotly.offline import get_plotlyjs

from lantern import data, figures, results
from lantern.config import Config, ConfigError, Plot, load_config
from lantern.results import Results

STATIC = files("lantern").joinpath("static")
ASSETS = {
    "/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/app.css": ("app.css", "text/css"),
    "/logo.svg": ("logo.svg", "image/svg+xml"),
}


class Session:
    """The results files at the sources and those added on the page, and what is drawn from each of their runs.

    Requests hold the lock, as the session is not thread-safe; a file loads within the request that adds or refreshes
    it, which holds up the other requests until it is loaded.
    """

    def __init__(self, sources: list[Path]) -> None:
        self.config: Config = load_config()
        self.sources = sources
        self.loaded: dict[str, Results] = {}
        self.added: dict[str, Results] = {}
        # the added files' contents, to prepare them again when the configuration is reloaded
        self._uploads: dict[str, bytes] = {}
        self.lock = threading.Lock()
        self._cache: dict = {}

    @property
    def files(self) -> dict[str, Results]:
        """Every loaded results file; one added on the page replaces one of the same name at the sources."""
        return self.loaded | self.added

    def add(self, content: bytes, name: str) -> None:
        """Load a results file added on the page."""
        self.added[name] = results.load(content, name, self.config.plots)
        self._uploads[name] = content
        self._cache.clear()

    def refresh(self) -> None:
        """Read the configuration again and load the results files at the sources as they are on disk now, in place of
        those loaded from there before, preparing the added files again; nothing changes if any is unreadable."""
        config = load_config()
        found = data.results_files(self.sources)
        loaded = {name: results.load(path, name, config.plots) for path, name in found}
        added = {name: results.load(content, name, config.plots) for name, content in self._uploads.items()}
        self.config, self.loaded, self.added = config, loaded, added
        self._cache.clear()

    def remove(self, name: str) -> None:
        """Unload a results file."""
        self.loaded.pop(name, None)
        self.added.pop(name, None)
        self._uploads.pop(name, None)
        self._cache.clear()

    @property
    def runs(self) -> list[str]:
        """Every loaded run, in the order of the files."""
        return [run for f in self.files.values() for run in f.runs]

    def short_names(self, runs: list[str]) -> dict[str, str]:
        """Each run's name within its file, in the order given; the full id where two files have a run of that name."""
        short = {run: run.removeprefix(f"{f.name}/") for f in self.files.values() for run in f.runs}

        return _distinct({run: short[run] for run in runs})

    def state(self) -> dict:
        """The files with their runs, and each run's display name, for the page."""
        files = [{"name": f.name, "compiled": f.compiled, "runs": f.runs} for f in self.files.values()]

        return {"files": files, "names": self._names(self.runs)}

    def catalogue(self, runs: list[str]) -> list[dict]:
        """The plots, with whether any of the runs has data for each and the views of a split plot, [value, title]."""
        def compute() -> list[dict]:
            return [
                {"id": p.id, "title": p.title, "section": p.section, "available": not self._lines(p, runs).is_empty(),
                 "nodes": [[n, self.config.labels.get(n, n)] for n in self._nodes(p, runs)]}
                for p in self.config.plots
            ]

        return self._cached(("catalogue", *runs), compute)

    def figure(self, plot_id: str, runs: list[str], node: str | None, panel: str | None = None) -> str:
        """One figure of the runs as Plotly JSON, or one panel of it enlarged; a split plot shows its first node by default."""
        return self._cached((plot_id, *runs, node, panel), lambda: self.draw(plot_id, runs, node, panel).to_json())

    def draw(self, plot_id: str, runs: list[str], node: str | None, panel: str | None = None) -> go.Figure:
        """One figure of the runs, or one panel of it enlarged; a split plot shows its first node by default."""
        plot = self.config.plot(plot_id)
        lines, _ = self._view(plot, runs, node)

        return figures.build(plot, lines, data.unit(plot, self._units()), self.config, self._names(runs), panel)

    def table(self, plot_id: str, runs: list[str], node: str | None, panel: str | None = None) -> tuple[str, str]:
        """The lines of a figure as CSV, with a file name: the plot's id and unit."""
        plot = self.config.plot(plot_id)
        lines, node = self._view(plot, runs, node)
        unit = data.unit(plot, self._units()).replace("/", " per ")
        parts = (plot_id, self.config.labels.get(node, node) if node else "", f"({unit})" if unit else "")
        name = " ".join(filter(None, parts))

        return figures.table(lines, self.config, self._names(runs), panel), f"{name}.csv"

    def panels(self, plot_id: str, runs: list[str], node: str | None = None) -> list[list[str]]:
        """The panels of a figure, [value, title], in the order drawn."""
        lines, _ = self._view(self.config.plot(plot_id), runs, node)

        return [[p, self.config.labels.get(p, p)] for p in figures.panels_of(lines, self.config)]

    def _lines(self, plot: Plot, runs: list[str]) -> pl.DataFrame:
        """The prepared lines of a plot of the runs, over all its views."""
        lines = [f.plots[plot.id] for f in self.files.values() if plot.id in f.plots and not set(f.runs).isdisjoint(runs)]

        return pl.concat(lines).filter(pl.col("run").is_in(runs)) if lines else pl.DataFrame(schema=data.LINES)

    def _view(self, plot: Plot, runs: list[str], node: str | None) -> tuple[pl.DataFrame, str | None]:
        """The lines of a plot of the runs in one view, the given node or else the first, and that node."""
        node = node or next(iter(self._nodes(plot, runs)), None)

        return self._lines(plot, runs).filter(pl.col("view") == (node or "")), node

    def _nodes(self, plot: Plot, runs: list[str]) -> list[str]:
        views = self._lines(plot, runs).get_column("view").unique().to_list()

        return sorted(v for v in views if v)

    def _names(self, runs: list[str]) -> dict[str, str]:
        """Each run's display name: that plots.yaml gives its name within its file, else that name; the full id where
        two are alike."""
        return _distinct({run: self.config.run_names.get(name, name) for run, name in self.short_names(runs).items()})

    def _units(self) -> dict[str, str]:
        return {k: v for f in self.files.values() for k, v in f.units.items()}

    def _cached[T](self, key: tuple, compute: Callable[[], T]) -> T:
        if key not in self._cache:
            self._cache[key] = compute()

        return self._cache[key]


def _distinct(names: dict[str, str]) -> dict[str, str]:
    """The names, with the key itself in place of a name two keys share."""
    counts = Counter(names.values())

    return {key: name if counts[name] == 1 else key for key, name in names.items()}


def make_server(session: Session, port: int) -> ThreadingHTTPServer:
    """An HTTP server for the session on localhost; port 0 picks a free one.

    Each connection gets a thread, so one a browser opens and never sends a request on holds up nothing but itself.
    """
    handler = type("Handler", (_Handler,), {"session": session})

    return ThreadingHTTPServer(("127.0.0.1", port), handler)


class _Handler(BaseHTTPRequestHandler):
    session: Session

    def do_GET(self) -> None:
        url = urlparse(self.path)
        path = unquote(url.path)
        params = parse_qs(url.query)
        query = {k: v[0] for k, v in params.items()}
        runs = params.get("run", [])

        if path == "/plotly.js":
            self._send(_plotly_js(), "text/javascript")

        elif path in ASSETS:
            name, content_type = ASSETS[path]
            self._send(STATIC.joinpath(name).read_bytes(), content_type)

        elif path == "/api/state":
            self._json(self._query(self.session.state))

        elif path == "/api/catalogue":
            self._json(self._query(self.session.catalogue, runs))

        elif path.startswith("/api/plots/") and path.endswith(".csv"):
            plot_id = path.removeprefix("/api/plots/").removesuffix(".csv")
            csv, name = self._query(self.session.table, plot_id, runs, query.get("node"), query.get("panel"))
            self._send(csv.encode(), "text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})

        elif path.startswith("/api/plots/"):
            plot_id = path.removeprefix("/api/plots/")
            figure = self._query(self.session.figure, plot_id, runs, query.get("node"), query.get("panel"))
            self._send(figure.encode(), "application/json")

        else:
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        try:
            if path == "/api/refresh":
                state = self._update(self.session.refresh)
            elif path == "/api/files":
                name = unquote(self.headers["X-Filename"])
                state = self._update(self.session.add, self.rfile.read(int(self.headers["Content-Length"])), name)
            else:
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return

        except (OSError, data.ResultsFileError, ConfigError) as e:
            self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
            return

        self._json(state)

    def do_DELETE(self) -> None:
        name = unquote(urlparse(self.path).path).removeprefix("/api/files/")
        self._json(self._update(self.session.remove, name))

    def _query[T](self, ask: Callable[..., T], *args: object) -> T:
        with self.session.lock:
            return ask(*args)

    def _update(self, change: Callable[..., None], *args: object) -> dict:
        """Change the session and read its state after as one step, so no request sees it half-changed."""
        with self.session.lock:
            change(*args)
            return self.session.state()

    def _json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send(json.dumps(value).encode(), "application/json", status)

    def _send(
        self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK, headers: dict[str, str] | None = None,
    ) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))

            for key, value in (headers or {}).items():
                self.send_header(key, value)

            self.end_headers()
            self.wfile.write(body)

        except (BrokenPipeError, ConnectionResetError):
            pass  # the browser dropped the connection, as a reload does to requests underway; there is no one to tell

    def log_message(self, *args: object) -> None:
        pass


@cache
def _plotly_js() -> bytes:
    return get_plotlyjs().encode()
