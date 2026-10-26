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
  configuration again and reloads PATH from disk. `--plots DIR` writes every
  plot of every run as SVG and CSV instead, SVG through the optional kaleido,
  and `--data FILE` writes the rows of the files as one CSV.
- A file is never read whole: on loading, Lantern reads a run at a time, only
  the series the plots name, and keeps each plot's lines.
- `plots.yaml` declares what is plotted and `labels.yaml` the names, colour
  names and order of the series. `theme.yaml` in the repository gives the
  Center's colours; it is not part of the package, which takes Plotly's
  colours. A series is `kind.attribute`, e.g. `fleet.newbuilds`, and
  `cumulative: true` sums a rate over the time steps up to each date.
  `per_gj: true` divides a per-ton value by the heating value of its
  fuel from the file's metadata, e.g. bunker prices and plant costs in USD/GJ.
- Clicking a panel of a multi-panel plot shows it alone; a select in the
  toolbar or Escape goes back to all panels. Long panel titles wrap. The
  plot and run columns resize by dragging their edges. The modebar downloads
  the plot as PNG or SVG and the drawn lines as CSV, a row per value.
- Compiled files: Lantern opens the compiled results file of a Horizon study,
  with a run per scenario, each a single summary. Each stacked plot also comes
  as lines, one panel per stacked series, followed by the stack as
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
