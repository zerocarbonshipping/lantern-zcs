# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""lantern [PATH ...]: open the viewer and load the results files at PATH, a folder loading every .parquet below it."""

import sys
import webbrowser
from pathlib import Path

from lantern.config import load_config
from lantern.server import Session, make_server

PORT = 8050


def main() -> int:
    """Serve the viewer, open it in the browser and load the given results in the background, the page showing the progress."""
    sources = [Path(arg) for arg in sys.argv[1:]]
    # only a missing path fails here; finding the files in a folder is part of the load
    missing = [f"'{path}'" for path in sources if not path.exists()]

    if missing:
        print(f"Error: no such file or folder: {', '.join(missing)}", file=sys.stderr)
        return 1

    session = Session(load_config(), sources)

    if sources:
        session.refresh()

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


if __name__ == "__main__":
    sys.exit(main())
