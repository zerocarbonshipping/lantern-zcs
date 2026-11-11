"""
The page and its JSON API, served on localhost.

The server takes a free port, never Lantern's 8050, so it does not clash with a Lantern running alongside.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import pytest

from lantern.server import make_server
from lantern.session import Session

if TYPE_CHECKING:
    from collections.abc import Iterator
    from email.message import Message
    from pathlib import Path


@pytest.fixture(scope="module")
def url(single: Path) -> Iterator[str]:
    """Serve a session of the single run, for the module."""
    server = make_server(Session([single]), 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://127.0.0.1:{server.server_address[1]}"

    server.shutdown()
    server.server_close()


def request(
    url: str, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None
) -> tuple[int, Message, bytes]:
    """Return the status, headers and body of the answer to a request."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, body, headers or {}, method=method), timeout=60) as answer:
            return answer.status, answer.headers, answer.read()

    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()


def api(url: str, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None) -> Any:
    """Return the JSON of a successful answer."""
    status, _, content = request(url, method, body, headers)

    assert status == 200, content

    return json.loads(content)


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/", "text/html"),
        ("/app.js", "text/javascript"),
        ("/buttons.js", "text/javascript"),
        ("/app.css", "text/css"),
        ("/logo.svg", "image/svg+xml"),
        ("/plotly.js", "text/javascript"),
    ],
)
def test_page(path: str, content_type: str, url: str) -> None:
    """The page and its assets are served, from the installed package."""
    status, headers, content = request(url + path)

    assert status == 200
    assert headers.get_content_type() == content_type
    assert content


def test_state(url: str) -> None:
    """The state lists the files and their runs, with each run's display name."""
    state = api(f"{url}/api/state")

    assert state == {
        "files": [{"name": "attribute_coverage", "compiled": False, "runs": ["attribute_coverage"]}],
        "names": {"attribute_coverage": "attribute_coverage"},
    }


def test_catalogue(url: str) -> None:
    """The catalogue lists every plot, with data for the run, and its views."""
    catalogue = api(f"{url}/api/catalogue?run=attribute_coverage")
    without_runs = api(f"{url}/api/catalogue")

    assert all(entry["available"] for entry in catalogue)
    assert not any(entry["available"] for entry in without_runs)
    assert [entry["id"] for entry in catalogue] == [entry["id"] for entry in without_runs]


def test_figure(url: str) -> None:
    """A plot of a run comes as Plotly JSON, its panels in its meta; one of no runs comes empty."""
    figure = api(f"{url}/api/plots/main_fuel_consumed?run=attribute_coverage&panel=hfo")
    empty = api(f"{url}/api/plots/main_fuel_consumed")

    assert figure["data"]
    assert {panel for panel, _ in figure["layout"]["meta"]["panels"]} >= {"hfo"}
    assert empty["data"] == []


def test_csv(url: str) -> None:
    """A plot's lines come as a CSV download named after the plot, its view and unit."""
    status, headers, content = request(f"{url}/api/plots/main_emission_absolute.csv?run=attribute_coverage")

    assert status == 200
    assert headers.get_content_type() == "text/csv"
    assert headers["Content-Disposition"].startswith('attachment; filename="main_emission_absolute')
    assert content.decode().startswith("run,panel,label,date,value\n")


def test_upload_and_remove(url: str, single: Path) -> None:
    """A file added on the page loads under its name, and goes again; a refresh keeps it."""
    added = api(f"{url}/api/files", "POST", single.read_bytes(), {"X-Filename": quote("my run")})
    refreshed = api(f"{url}/api/refresh", "POST")
    removed = api(f"{url}/api/files/{quote('my run')}", "DELETE")

    assert [f["name"] for f in added["files"]] == ["attribute_coverage", "my run"]
    assert refreshed == added
    assert [f["name"] for f in removed["files"]] == ["attribute_coverage"]


@pytest.mark.parametrize(
    ("method", "path", "body", "status", "message"),
    [
        ("POST", "/api/files", b"not parquet", 400, "'bad' is not a Navigate results file"),
        ("GET", "/api/plots/no_such_plot", None, 400, "no plot 'no_such_plot' in plots.yaml"),
        ("GET", "/no/such/path", None, 404, "not found"),
        ("POST", "/no/such/path", None, 404, "not found"),
        ("DELETE", "/no/such/path", None, 404, "not found"),
    ],
)
def test_errors(url: str, method: str, path: str, body: bytes | None, status: int, message: str) -> None:
    """A request that cannot be answered gets its status and a message for the page."""
    answer = request(url + path, method, body, {"X-Filename": "bad"})

    assert answer[0] == status
    assert json.loads(answer[2]) == {"error": message}
