# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""lantern [PATH ...]: open the viewer with the results files at PATH, a folder loading every .parquet below it."""

import sys
import threading
import webbrowser
from pathlib import Path

from lantern.config import load_config
from lantern.data import ResultsFileError
from lantern.server import Session, make_server

PORT = 8050


def main() -> int:
    """Load the given results, serve the viewer and open it in the browser."""
    session = Session(load_config(), [Path(arg) for arg in sys.argv[1:]])

    try:
        session.refresh()
    except (OSError, ResultsFileError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    for name in session.runs:
        print(f"Loaded {name}", flush=True)

    try:
        server = make_server(session, PORT)
    except OSError:
        server = make_server(session, 0)

    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Lantern is running at {url} (Ctrl+C to stop)", flush=True)
    threading.Timer(0.5, webbrowser.open, (url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
