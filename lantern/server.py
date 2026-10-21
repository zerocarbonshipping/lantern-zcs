# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Serve the page and its JSON API on localhost; results files load in the background while the page shows the progress."""

from __future__ import annotations

import json
import sys
import threading
from collections.abc import Callable, Iterator
from functools import cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import polars as pl
from plotly.offline import get_plotlyjs

from lantern import data, figures, results
from lantern.config import Config, Plot
from lantern.results import Results

STATIC = files("lantern").joinpath("static")
ASSETS = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/app.css": ("app.css", "text/css")}



class Session:
    """The results files at the sources and those added on the page, and what is drawn from each of their runs.

    Requests hold the lock, as the session is not thread-safe. A file loads in a thread of its own, one load at a
    time, without the lock, so the page keeps working and polls the progress; the lock is taken only to put a file
    in place as each of its plots is prepared, which counts up the version, so the page takes it. A load reports its
    progress and error by plain assignment, which needs no lock.
    """

    def __init__(self, config: Config, sources: list[Path]) -> None:
        self.config = config
        self.sources = sources
        self.loaded: dict[str, Results] = {}
        self.added: dict[str, Results] = {}
        self.lock = threading.RLock()
        self._cache: dict = {}
        # loads run in daemon threads, so Ctrl+C stops Lantern without waiting for one underway
        self._loads: list[threading.Thread] = []
        self._one_load = threading.Lock()
        self._progress: dict = {}
        self._error: str | None = None
        self._version = 0

    @property
    def files(self) -> dict[str, Results]:
        """Every loaded results file; one added on the page replaces one of the same name at the sources."""
        return self.loaded | self.added

    def add(self, content: bytes, name: str) -> None:
        """Start loading a results file added on the page."""
        def load() -> None:
            for file in self._load(content, name, 1, 1):
                with self.lock:
                    self.added[name] = file
                    self._changed()

        self._start(load)

    def refresh(self) -> None:
        """Start loading the results files at the sources as they are on disk now, each replacing its old version as
        it loads; files no longer there go once all have loaded."""
        def load() -> None:
            found = data.results_files(self.sources)

            for index, (path, name) in enumerate(found):
                for file in self._load(path, name, index + 1, len(found)):
                    with self.lock:
                        self.loaded[name] = file
                        self._changed()

            names = {name for _, name in found}

            with self.lock:
                self.loaded = {k: v for k, v in self.loaded.items() if k in names}
                self._changed()

        self._start(load)

    def remove(self, name: str) -> None:
        """Unload a results file."""
        self.loaded.pop(name, None)
        self.added.pop(name, None)
        self._changed()

    def state(self) -> dict:
        """The files with their runs, samples, the representative sample of each ensemble and whether they are still
        loading, the version of the files, the progress of loading, {text, done, total}, while a load is underway or
        waiting, and the error of the last one that failed; a file whose load failed is not loading."""
        loading = self._progress if any(load.is_alive() for load in self._loads) else None
        files = [
            {"name": f.name, "compiled": f.compiled, "runs": f.runs, "representatives": f.representatives,
             "loading": bool(loading) and not f.complete}
            for f in self.files.values()
        ]
        refreshable = bool(self.sources)

        return {"files": files, "version": self._version, "refreshable": refreshable, "loading": loading, "error": self._error}

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
        plot = self.config.plot(plot_id)
        node = node or next(iter(self._nodes(plot, runs)), None)

        def draw() -> str:
            lines = self._lines(plot, runs).filter(pl.col("view") == (node or "")).drop("view")
            unit = data.unit(plot, self._units())
            return figures.build(plot, lines, unit, self.config, self._names(runs), panel).to_json()

        return self._cached((plot_id, *runs, node, panel), draw)

    def _start(self, load: Callable[[], None]) -> None:
        """Run a load, which publishes what it loads, in a thread of its own after any underway."""
        def work() -> None:
            with self._one_load:
                try:
                    load()
                # any failure, not only an unreadable file, ends the load, so the page stops waiting and shows it
                except Exception as e:
                    self._error = str(e) or type(e).__name__
                    print(f"Error: {self._error}", file=sys.stderr, flush=True)

        with self.lock:
            self._loads = [load for load in self._loads if load.is_alive()]

            if not self._loads:
                self._report("Starting to load")

            self._error = None
            self._loads.append(threading.Thread(target=work, daemon=True))
            self._loads[-1].start()

    def _load(self, source: Path | bytes, name: str, index: int, count: int) -> Iterator[Results]:
        """Load a results file, the index-th of count, reporting its progress; it is yielded as each plot is prepared."""
        file = f"{name} ({index}/{count})" if count > 1 else name

        def progress(step: str, done: int, total: int) -> None:
            self._report(f"Loading {file} · {step}", done, total)

        return results.load(source, name, self.config.plots, progress)

    def _changed(self) -> None:
        """Forget what was drawn from the files and count up their version, so the page takes them anew."""
        self._cache.clear()
        self._version += 1

    def _report(self, text: str, done: int = 0, total: int = 0) -> None:
        self._progress = {"text": text, "done": done, "total": total}

    def _lines(self, plot: Plot, runs: list[str]) -> pl.DataFrame:
        """The prepared lines of a plot of the runs, over all its views."""
        lines = [f.plots[plot.id] for f in self.files.values() if plot.id in f.plots and not f.runs.keys().isdisjoint(runs)]

        return pl.concat(lines).filter(pl.col("run").is_in(runs)) if lines else pl.DataFrame()

    def _nodes(self, plot: Plot, runs: list[str]) -> list[str]:
        lines = self._lines(plot, runs)

        return [] if lines.is_empty() else sorted(v for v in lines.get_column("view").unique().to_list() if v)

    def _names(self, runs: list[str]) -> dict[str, str]:
        """Each run's name in a figure: that within its compiled file, or the file's; the full one where two are alike."""
        short = {run: run.removeprefix(f"{f.name}/") for f in self.files.values() for run in f.runs if run in runs}
        names = list(short.values())

        return {run: short[run] if names.count(short[run]) == 1 else run for run in runs}

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

        except OSError as e:
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
