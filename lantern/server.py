# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Serve the page and its JSON API on localhost; the loaded files are the only state, used by one request at a time."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from functools import cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import polars as pl
from plotly.offline import get_plotlyjs

from lantern import data, figures, representative
from lantern.config import Config, Plot

STATIC = files("lantern").joinpath("static")
ASSETS = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/app.css": ("app.css", "text/css")}


class Session:
    """The results files at the sources and those added on the page, and what is drawn from each of their runs."""

    def __init__(self, config: Config, sources: list[Path]) -> None:
        self.config = config
        self.sources = sources
        self.loaded: dict[str, data.ResultsFile] = {}
        self.added: dict[str, data.ResultsFile] = {}
        self._cache: dict = {}

    @property
    def files(self) -> dict[str, data.ResultsFile]:
        """Every loaded results file; one added on the page replaces one of the same name at the sources."""
        return self.loaded | self.added

    def add(self, content: bytes, name: str) -> None:
        """Load a results file added on the page."""
        self.added[name] = data.read_file(content, name)
        self._cache.clear()

    def refresh(self, progress: Callable[[int, int, str], None] | None = None) -> None:
        """Load the results files at the sources as they are on disk now; nothing changes if one is unreadable.

        progress, if given, is told before each file how many of how many are read and which comes next.
        """
        found = data.results_files(self.sources)
        files = {}

        for done, (path, name) in enumerate(found):
            if progress:
                progress(done, len(found), name)

            files[name] = data.read_file(path.read_bytes(), name)

        self.loaded = files
        self._cache.clear()

    def remove(self, name: str) -> None:
        """Unload a results file."""
        self.loaded.pop(name, None)
        self.added.pop(name, None)
        self._cache.clear()

    def state(self) -> dict:
        """The loaded files with their runs, samples and the representative sample of each ensemble, for the page."""
        files = [{
            "name": f.name, "compiled": f.compiled, "runs": f.runs,
            "representatives": {run: self._representative(run) for run in f.runs},
        } for f in self.files.values()]

        return {"files": files, "refreshable": bool(self.sources)}

    def catalogue(self, runs: list[str]) -> list[dict]:
        """The plots, with whether any of the runs has data for each and the views of a split plot, [value, title]."""
        def compute() -> list[dict]:
            frames = [self._frame(run) for run in runs]
            return [
                {"id": p.id, "title": p.title, "section": p.section, "available": any(data.has_data(p, f) for f in frames),
                 "nodes": [[n, self.config.labels.get(n, n)] for n in self._nodes(p, runs)]}
                for p in self.config.plots
            ]

        return self._cached(("catalogue", *runs), compute)

    def figure(self, plot_id: str, runs: list[str], node: str | None, panel: str | None = None) -> str:
        """One figure of the runs as Plotly JSON, or one panel of it enlarged; a split plot shows its first node by default."""
        plot = self.config.plot(plot_id)
        node = node or next(iter(self._nodes(plot, runs)), None)

        def draw() -> str:
            series = pl.concat([self._series(plot, run, node) for run in runs])
            unit = data.unit(plot, self._units())
            return figures.build(plot, series, unit, self.config, self._names(runs), panel).to_json()

        return self._cached((plot_id, *runs, node, panel), draw)

    def _series(self, plot: Plot, run: str, node: str | None) -> pl.DataFrame:
        def compute() -> pl.DataFrame:
            return data.prepare(plot, self._frame(run), node, self._representative(run)).with_columns(run=pl.lit(run))

        return self._cached(("series", plot.id, run, node), compute)

    def _representative(self, run: str) -> str | None:
        return self._cached(("representative", run), lambda: representative.choose(self.config.plots, self._frame(run)))

    def _nodes(self, plot: Plot, runs: list[str]) -> list[str]:
        return sorted({n for run in runs for n in data.split_nodes(plot, self._frame(run))})

    def _names(self, runs: list[str]) -> dict[str, str]:
        """Each run's name in a figure: that within its compiled file, or the file's; the full one where two are alike."""
        short = {run: run.removeprefix(f"{f.name}/") for f in self.files.values() for run in f.runs if run in runs}
        names = list(short.values())

        return {run: short[run] if names.count(short[run]) == 1 else run for run in runs}

    def _frame(self, run: str) -> pl.DataFrame:
        file = next(f for f in self.files.values() if run in f.runs)

        return self._cached(("frame", run), lambda: file.frame.filter(pl.col("run") == run))

    def _units(self) -> dict[str, str]:
        return {k: v for f in self.files.values() for k, v in f.units.items()}

    def _cached(self, key, compute):
        if key not in self._cache:
            self._cache[key] = compute()

        return self._cache[key]


def make_server(session: Session, port: int) -> ThreadingHTTPServer:
    """An HTTP server for the session on localhost; port 0 picks a free one.

    Each connection gets a thread, so one a browser opens and never sends a request on holds up nothing but itself.
    """
    handler = type("Handler", (_Handler,), {"session": session, "lock": threading.Lock()})

    return ThreadingHTTPServer(("127.0.0.1", port), handler)


class _Handler(BaseHTTPRequestHandler):
    session: Session
    lock: threading.Lock  # the session is not thread-safe: it serves one request at a time, only the socket I/O overlaps

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

        except (OSError, data.ResultsFileError) as e:
            self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
            return

        self._json(state)

    def do_DELETE(self) -> None:
        name = unquote(urlparse(self.path).path).removeprefix("/api/files/")
        self._json(self._update(self.session.remove, name))

    def _query[T](self, ask: Callable[..., T], *args: object) -> T:
        with self.lock:
            return ask(*args)

    def _update(self, change: Callable[..., None], *args: object) -> dict:
        """Change the session and read its state after as one step, so no request sees it half-changed."""
        with self.lock:
            change(*args)
            return self.session.state()

    def _json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send(json.dumps(value).encode(), "application/json", status)

    def _send(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        except (BrokenPipeError, ConnectionResetError):
            pass  # the browser dropped the connection, as a reload does to requests underway; there is no one to tell

    def log_message(self, *args: object) -> None:
        pass


@cache
def _plotly_js() -> bytes:
    return get_plotlyjs().encode()
