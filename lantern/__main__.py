# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""lantern [PATH ...]: open the viewer with the results files at PATH, a folder loading every .parquet below it; with
--plots DIR or --data FILE, write the plots or the rows to files instead of serving them."""

import argparse
import sys
import webbrowser
from pathlib import Path

from lantern import export
from lantern.config import ConfigError
from lantern.data import ResultsFileError
from lantern.server import Session, make_server

PORT = 8050


def main() -> int:
    """Load the given results and serve the viewer in the browser, or write the plots or the rows to files."""
    parser = argparse.ArgumentParser(prog="lantern", description="Browser viewer for Navigate results files.")
    parser.add_argument("paths", nargs="*", type=Path, metavar="PATH", help="results files, or folders of them")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--plots", type=Path, metavar="DIR", help="write every plot of every run as SVG and CSV into DIR")
    output.add_argument("--data", type=Path, metavar="FILE", help="write the rows of the results files as one CSV")
    args = parser.parse_args()

    try:
        if args.data:
            export.rows(args.paths, args.data)
            return 0

        session = Session(args.paths)
        session.refresh()

        if args.plots:
            export.plots(session, args.plots)
            return 0

    except (OSError, ResultsFileError, ConfigError, export.ExportError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

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
