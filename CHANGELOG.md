<!--
SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
SPDX-License-Identifier: CC-BY-4.0
-->

# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - Unreleased

Lantern 2 is a rewrite: a local web app for the Parquet results file every
Navigate run writes.

### Added
- `lantern [PATH ...]` opens the viewer in the browser with the results files
  at PATH; a folder loads every `.parquet` file below it.
  Files can also be added on the page, and a Refresh button reads the
  configuration again and reloads PATH from disk. `--plot ID[RUN,...][PANEL]`
  writes one plot as PNG into `plots/` instead, through the optional kaleido
  and with a progress bar, of each run or of the runs in brackets together,
  and only one panel if named, by the ids and panels `--list` prints.
  `--data` writes the rows of the files as `data.csv`.
- A file is never read whole: on loading, Lantern reads a run at a time, only
  the series the plots name, and keeps each plot's lines. Polars runs on one
  thread unless `POLARS_MAX_THREADS` says otherwise, as its many small queries
  load a file of many runs up to ten times slower on all cores.
- `plots.yaml`, read from the folder Lantern is started in or else from the
  home folder, declares what is plotted; the packaged `labels.yaml` gives the
  names, colour names and order of the series and `theme.yaml` the Center's
  colours, the palettes of its chart in shades 0 to 8, and the figures' font.
  The `labels` and `theme` keys of `plots.yaml` override their entries. A series is `kind.attribute`, e.g. `fleet.newbuilds`, and
  `cumulative: true` sums a rate over the time steps up to each date.
  `per_gj: true` divides a per-ton value by the heating value of its
  fuel from the file's metadata, e.g. bunker prices and plant costs in USD/GJ.
- Clicking a panel of a multi-panel plot shows it alone; a select in the
  toolbar or Escape goes back to all panels. Long panel titles wrap. The
  plot and run columns resize by dragging their edges. The modebar downloads
  the plot as PNG or SVG and the drawn lines as CSV, a row per value.
- Compiled files: Lantern opens the compiled results file of a Horizon study,
  with a run per scenario: its representative sample, drawn as the line, and
  the summary runs Horizon writes with it and names in the file's metadata
  under `summaries`, drawn as a dashed median and a band behind the line, and left out of a
  stack. The CSV download carries them as columns. Each stacked plot also
  comes as lines, one panel per stacked series, followed by the stack as
  "<title> (Stacked)".
  Runs are listed in the sidebar, compiled files marked; Ctrl-click compares
  runs, overlaid in a colour each, or for stacks and plots that tell series
  apart by colour, in a column of panels per run with a shared y axis. An
  selected run's colour highlights it in the sidebar; `customize_runs` in
  `plots.yaml` gives a run a display name and a colour.

### Removed
- The report CSV input, all command-line options, the HTML and PNG outputs,
  the representative runs, percentile bands and representatives CSV, the
  `weight` plot key, and the pandas, numpy, kaleido and tqdm dependencies.

## [1.0.0] - 2026-08-18

Initial public release of Lantern, an open-source visualization tool for
scenario ensembles from the
[Navigate](https://github.com/zerocarbonshipping/navigate-zcs) maritime
transition model.
