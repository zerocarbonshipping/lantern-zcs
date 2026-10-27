# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""lantern [PATH ...]: open the viewer with the results files at PATH, a folder loading every .parquet below it; with
--plot or --data, write a plot to plots/ or the rows to data.csv in the current folder instead of serving them. --plot
draws one plot, of each run or of runs together, by the ids --list prints."""

import argparse
import re
import sys
import webbrowser
from pathlib import Path

from lantern import export
from lantern.config import ConfigError
from lantern.data import ResultsFileError
from lantern.server import Session, make_server

PORT = 8050
PLOTS = Path("plots")
DATA = Path("data.csv")
# a plot id, then optionally runs in brackets: fleet_speed or fleet_speed[e2e/nzf_main,e2e/strict_all]
_PLOT = re.compile(r"([^\[\],]+)(?:\[([^\[\]]*)\])?")


def _plot(value: str) -> tuple[str, list[str] | None]:
    """argparse type: a plot id and the runs in its brackets, or None without brackets."""
    match = _PLOT.fullmatch(value.strip())

    if not match:
        raise argparse.ArgumentTypeError(f"expected ID or ID[RUN,...], got {value!r}")

    plot_id, inside = match.groups()

    if inside is None:
        return plot_id.strip(), None

    runs = [run.strip() for run in inside.split(",") if run.strip()]

    if not runs:
        raise argparse.ArgumentTypeError(f"no runs in the brackets of {value!r}")

    return plot_id.strip(), runs


def main() -> int:
    """Load the given results and serve the viewer in the browser, or write the plots or the rows to files."""
    parser = argparse.ArgumentParser(prog="lantern", description="Browser viewer for Navigate results files.")
    parser.add_argument("paths", nargs="*", type=Path, metavar="PATH", help="results files, or folders of them")
    parser.add_argument("--plot", action="append", type=_plot, metavar="ID[RUN,...]",
                        help=f"write one plot as PNG into {PLOTS}/, of each run, or of the runs in brackets drawn "
                             "together; repeat it for more, by the ids and runs --list prints, and quote it where the "
                             "shell expands []")
    parser.add_argument("--list", action="store_true", help="print the runs and the ids of the plots with data")
    parser.add_argument("--data", action="store_true", help=f"write the rows of the results files as one CSV, {DATA}")
    args = parser.parse_args()

    try:
        if args.data:
            export.rows(args.paths, DATA)

        if args.data and not (args.plot or args.list):
            return 0

        session = Session(args.paths)
        session.refresh()

        if args.list:
            sys.stdout.write(export.listing(session))

        if args.plot:
            export.plots(session, PLOTS, args.plot)

        if args.plot or args.list:
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
