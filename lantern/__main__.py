# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""lantern [PATH ...]: open the viewer with the results files at PATH, a folder loading every .parquet below it."""

import shutil
import sys
import webbrowser
from pathlib import Path

from lantern.config import load_config
from lantern.data import ResultsFileError
from lantern.server import Session, make_server

PORT = 8050
CLEAR = "\r\x1b[K"  # back to the start of the line and clear it, to redraw the progress bar in place


def main() -> int:
    """Load the given results, serve the viewer and open it in the browser."""
    session = Session(load_config(), [Path(arg) for arg in sys.argv[1:]])

    try:
        session.refresh(_progress)
    except (OSError, ResultsFileError) as e:
        print(f"{CLEAR}Error: {e}", file=sys.stderr)
        return 1

    if session.files:
        print(f"{CLEAR}Loaded {len(session.files)} results file(s)", flush=True)

    try:
        server = make_server(session, PORT)
    except OSError:
        server = make_server(session, 0)

    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Lantern is running at {url} (Ctrl+C to stop)", flush=True)
    # the server already listens, so the browser's request waits until it serves
    webbrowser.open(url)

    with server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

    return 0


def _progress(done: int, total: int, name: str) -> None:
    # a line wider than the terminal wraps, and the wrapped part could not be redrawn
    bar = "#" * (20 * done // total)
    line = f"Loading [{bar:<20}] {done}/{total} {name}"
    print(CLEAR + line[: shutil.get_terminal_size().columns - 1], end="", flush=True)


if __name__ == "__main__":
    sys.exit(main())
