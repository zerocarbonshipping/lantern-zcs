"""Serve the page and its JSON API on localhost; the session is the only state, used by one request at a time."""

from __future__ import annotations

import json
from functools import cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, unquote, urlparse

from plotly.offline import get_plotlyjs

from lantern.config import ConfigError
from lantern.data import ResultsFileError

if TYPE_CHECKING:
    from collections.abc import Callable

    from lantern.session import Session

STATIC = files("lantern").joinpath("static")
ASSETS = {
    "/": ("index.html", "text/html"),
    "/app.js": ("app.js", "text/javascript"),
    "/app.css": ("app.css", "text/css"),
    "/logo.svg": ("logo.svg", "image/svg+xml"),
}


def make_server(session: Session, port: int) -> ThreadingHTTPServer:
    """
    Make an HTTP server for the session on localhost; port 0 picks a free one.

    Each connection gets a thread, so one a browser opens and never sends a request on holds up nothing but itself.
    """
    handler = type("Handler", (_Handler,), {"session": session})

    return ThreadingHTTPServer(("127.0.0.1", port), handler)


class _Handler(BaseHTTPRequestHandler):
    session: Session

    def do_GET(self) -> None:
        self._answer(self._get)

    def do_POST(self) -> None:
        self._answer(self._post)

    def do_DELETE(self) -> None:
        self._answer(self._delete)

    def _answer(self, route: Callable[[str, dict[str, list[str]]], None]) -> None:
        """Route a request by its path and query; an error the user can fix goes back to the page as its message."""
        url = urlparse(self.path)

        try:
            route(unquote(url.path), parse_qs(url.query))
        except (OSError, ResultsFileError, ConfigError) as e:
            self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)

    def _get(self, path: str, params: dict[str, list[str]]) -> None:
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
            csv, name = self._query(self.session.table, plot_id, runs, query.get("view"), query.get("panel"))
            self._send(csv.encode(), "text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})

        elif path.startswith("/api/plots/"):
            plot_id = path.removeprefix("/api/plots/")
            figure = self._query(self.session.figure, plot_id, runs, query.get("view"), query.get("panel"))
            self._send(figure.encode(), "application/json")

        else:
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def _post(self, path: str, params: dict[str, list[str]]) -> None:
        if path == "/api/refresh":
            self._json(self._update(self.session.refresh))

        elif path == "/api/files":
            content = self.rfile.read(int(self.headers["Content-Length"]))
            self._json(self._update(self.session.add, content, unquote(self.headers["X-Filename"])))

        else:
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def _delete(self, path: str, params: dict[str, list[str]]) -> None:
        if not path.startswith("/api/files/"):
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return

        self._json(self._update(self.session.remove, path.removeprefix("/api/files/")))

    def _query[T](self, ask: Callable[..., T], *args: object) -> T:
        with self.session.lock:
            return ask(*args)

    def _update(self, change: Callable[..., None], *args: object) -> dict[str, object]:
        """Change the session and read its state after as one step, so no request sees it half-changed."""
        with self.session.lock:
            change(*args)
            return self.session.state()

    def _json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send(json.dumps(value).encode(), "application/json", status)

    def _send(
        self,
        body: bytes,
        content_type: str,
        status: HTTPStatus = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
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
    script: str = get_plotlyjs()

    return script.encode()
