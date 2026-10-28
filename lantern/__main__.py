# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""lantern [PATH ...]: open the viewer with the results files at PATH, a folder loading every .parquet below it; with
--plot or --data, write a plot to plots/ or the rows to data.csv in the current folder instead of serving them. --plot
draws one plot, or one panel of it, of each run or of runs together, by the ids --list prints."""

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
# a plot id, then optionally runs in brackets and a panel in brackets: fleet_speed, fleet_speed[e2e/nzf_main,e2e/strict_all]
# or fleet_speed[][Ferry]
_PLOT = re.compile(r"([^\[\],]+)(?:\[([^\[\]]*)\](?:\[([^\[\]]*)\])?)?")


def _plot(value: str) -> export.Spec:
    """argparse type: a plot id, the runs in its first brackets, None for each run, and the panel in its second."""
    match = _PLOT.fullmatch(value.strip())

    if not match:
        raise argparse.ArgumentTypeError(f"expected ID, ID[RUN,...] or ID[RUN,...][PANEL], got {value!r}")

    plot_id, inside, panel = match.groups()
    runs = [run.strip() for run in inside.split(",") if run.strip()] if inside else None

    return plot_id.strip(), runs, panel.strip() if panel else None


def main() -> int:
    """Load the given results and serve the viewer in the browser, or write the plots or the rows to files."""
    parser = argparse.ArgumentParser(prog="lantern", description="Browser viewer for Navigate results files.")
    parser.add_argument("paths", nargs="*", type=Path, metavar="PATH", help="results files, or folders of them")
    parser.add_argument("--plot", action="append", type=_plot, metavar="ID[RUN,...][PANEL]",
                        help=f"write one plot as PNG into {PLOTS}/, of each run, or of the runs in brackets drawn "
                             "together, and only the panel in the second brackets if given; repeat it for more, by the "
                             "ids, runs and panels --list prints, and quote it where the shell expands []")
    parser.add_argument("--list", action="store_true",
                        help="print the runs and the ids and panels of the plots with data")
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
