# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Write what the viewer shows to files instead of serving it: every plot of every run as SVG and CSV, or the rows of the
results files as one CSV."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from lantern import data
from lantern.server import Session

_WIDTH = 1600  # px, of an exported figure; the height follows its rows of panels


class ExportError(Exception):
    """An export that cannot be written."""


def plots(session: Session, folder: Path) -> None:
    """Write every plot of every loaded run, in each of its views, as <folder>/<run>/<plot>[_<node>].svg and .csv."""
    for file in session.files.values():
        for run in file.runs:
            target = folder / run
            target.mkdir(parents=True, exist_ok=True)
            count = 0

            for entry in session.catalogue([run]):
                if not entry["available"]:
                    continue

                for node, _ in entry["nodes"] or [(None, None)]:
                    name = f"{entry['id']}_{node}" if node else entry["id"]
                    figure = session.draw(entry["id"], [run], node)
                    figure.update_layout(width=_WIDTH)
                    _write_svg(figure, target / f"{name}.svg")
                    csv, _ = session.table(entry["id"], [run], node)
                    (target / f"{name}.csv").write_text(csv, "utf-8")
                    count += 1

            print(f"Wrote {count} plots of {run} to {target}", flush=True)


def rows(sources: list[Path], path: Path) -> None:
    """Write the rows of the results files at the sources, every series and date, as one CSV: run, kind, node,
    attribute, key1, key2, date, value."""
    frames = []

    for file, name in data.results_files(sources):
        scan = pl.scan_parquet(file)
        schema = scan.collect_schema()

        if missing := set(data.COLUMNS) - set(schema):
            raise data.ResultsFileError(f"'{name}' lacks the columns {', '.join(sorted(missing))}")

        run = pl.concat_str([pl.lit(f"{name}/"), pl.col("run")]) if "run" in schema else pl.lit(name)
        labels = [pl.col(c).cast(pl.String) for c in data.LABELS]
        frames.append(scan.select(run.alias("run"), *labels, "date", pl.col("value").cast(pl.Float64)))

    if not frames:
        raise data.ResultsFileError("no results files to write")

    pl.concat(frames).sink_csv(path)
    print(f"Wrote the rows of {len(frames)} file(s) to {path}", flush=True)


def _write_svg(figure, path: Path) -> None:
    try:
        figure.write_image(path, format="svg")

    except Exception as e:  # noqa: BLE001 - kaleido and its browser fail in many ways, each with its own message
        raise ExportError(
            f"cannot write {path}: SVG export needs kaleido and Chrome; pip install 'lantern-zcs[export]' and run "
            f"plotly_get_chrome once\n{e}"
        ) from e
