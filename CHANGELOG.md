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
  at PATH; a folder loads every `.parquet` file below it. Files can also be
  added on the page, and a Refresh button reloads PATH from disk.
- `plots.toml` declares what is plotted and `style.toml` how it looks, in the
  Center's colours.
- Clicking a panel of a multi-panel plot shows it alone; a select in the
  toolbar or Escape goes back to all panels. Long panel titles wrap.
- Ensembles: Lantern opens the compiled results file of a Horizon study, with
  a run per scenario and its samples, and draws an ensemble's lines and areas
  as the median with a 5th to 95th percentile band, and stacks as medians.
  Each stacked plot also comes as lines, one panel per stacked series with
  its band, followed by the stack as "<title> (Stacked)".
  Runs are listed in the sidebar, compiled files marked; Ctrl-click compares
  runs, overlaid in a colour each, or for stacks and plots that tell series
  apart by colour, in a column of panels per run with a shared y axis.

### Removed
- The report CSV input, all command-line options, the HTML and PNG outputs,
  representative selection, and the pandas, numpy, kaleido and tqdm
  dependencies.

## [1.0.0] - 2026-08-18

Initial public release of Lantern, an open-source visualization tool for
scenario ensembles from the
[Navigate](https://github.com/zerocarbonshipping/navigate-zcs) maritime
transition model.
