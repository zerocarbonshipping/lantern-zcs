# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Serve the page and its JSON API on localhost, one request at a time; the loaded runs are the only state."""

from __future__ import annotations

import json
from functools import cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.resources import files
from urllib.parse import parse_qs, unquote, urlparse

import polars as pl
from plotly.offline import get_plotlyjs

from lantern import data, figures
from lantern.config import Config

STATIC = files("lantern").joinpath("static")
TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}


class Session:
    """The loaded runs, and what is drawn from them."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.runs: dict[str, data.Run] = {}
        self._cache: dict = {}

    def add(self, content: bytes, name: str) -> None:
        """Load a results file, replacing a run of the same name."""
        self.runs[name] = data.read_run(content, name)
        self._cache.clear()

    def remove(self, name: str) -> None:
        """Unload a run."""
        self.runs.pop(name, None)
        self._cache.clear()

    def state(self) -> dict:
        """The loaded runs and the catalogue, for the page."""
        if not self.runs:
            return {"runs": [], "plots": []}

        return {"runs": list(self.runs), "plots": self._cached("plots", self._catalogue)}

    def figure(self, plot_id: str, node: str | None) -> str:
        """One figure as Plotly JSON; a split plot shows its first node by default."""
        plot = self.config.plot(plot_id)
        node = node or next(iter(data.split_nodes(plot, self._frame())), None)

        def draw() -> str:
            series = data.prepare(plot, self._frame(), node)
            return figures.build(plot, series, data.unit(plot, self._units()), self.config).to_json()

        return self._cached((plot_id, node), draw)

    def _catalogue(self) -> list[dict]:
        frame = self._frame()

        return [
            {"id": p.id, "title": p.title, "section": p.section, "available": data.has_data(p, frame),
             "nodes": data.split_nodes(p, frame)}
            for p in self.config.plots
        ]

    def _frame(self) -> pl.DataFrame:
        return self._cached("frame", lambda: pl.concat([run.frame for run in self.runs.values()]))

    def _units(self) -> dict[str, str]:
        return {k: v for run in self.runs.values() for k, v in run.units.items()}

    def _cached(self, key, compute):
        if key not in self._cache:
            self._cache[key] = compute()

        return self._cache[key]


def make_server(session: Session, port: int) -> HTTPServer:
    """An HTTP server for the session on localhost; port 0 picks a free one."""
    return HTTPServer(("127.0.0.1", port), type("Handler", (_Handler,), {"session": session}))


class _Handler(BaseHTTPRequestHandler):
    session: Session

    def do_GET(self) -> None:
        url = urlparse(self.path)
        path = "/static/index.html" if url.path == "/" else unquote(url.path)
        node = parse_qs(url.query).get("node", [None])[0]
        asset = path.removeprefix("/static/")

        if path == "/plotly.js":
            self._send(_plotly_js(), "text/javascript")

        elif path.startswith("/static/") and ".." not in asset and STATIC.joinpath(asset).is_file():
            self._send(STATIC.joinpath(asset).read_bytes(), TYPES.get(asset[asset.rfind("."):], "text/plain"))

        elif path == "/api/state":
            self._json(self.session.state())

        elif path.startswith("/api/plots/"):
            try:
                self._send(self.session.figure(path.removeprefix("/api/plots/"), node).encode(), "application/json")
            except KeyError:
                self._json({"error": "unknown plot"}, HTTPStatus.NOT_FOUND)

        else:
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        name = unquote(self.headers.get("X-Filename", "run")).removesuffix(".parquet")

        try:
            self.session.add(self.rfile.read(int(self.headers["Content-Length"])), name)
        except data.ResultsFileError as e:
            self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
            return

        self._json(self.session.state())

    def do_DELETE(self) -> None:
        self.session.remove(unquote(urlparse(self.path).path).removeprefix("/api/runs/"))
        self._json(self.session.state())

    def _json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send(json.dumps(value).encode(), "application/json", status)

    def _send(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


@cache
def _plotly_js() -> bytes:
    return get_plotlyjs().encode()
