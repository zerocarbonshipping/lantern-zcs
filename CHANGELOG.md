<!--
SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
SPDX-License-Identifier: CC-BY-4.0
-->

# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - Unreleased

Lantern 2 is a rewrite: a local web app for the Parquet results files
Navigate writes.

### Added
- `lantern [PATH ...]` opens the viewer in the browser on the results files
  at PATH, a folder loading every `.parquet` below it. Files can be added and
  unloaded on the page; Refresh reloads the configuration and PATH from disk.
- `--plot ID[RUN,...][PANEL]` writes a plot, of each run or of runs together,
  as an interactive HTML page; `--list` prints the plot ids and panels, and
  `--data` writes every row as one CSV.
- `plots.yaml`, from the working folder or the home folder, declares the
  plots, and can list a stack also as lines, a panel per series. The packaged
  `labels.yaml` and `theme.yaml` name, order and colour the series, and
  `plots.yaml` can override their entries. See `PLOTS.md`.
- Compiled files of Horizon studies: a run per scenario, drawn with the
  median and band of its samples where the file names summary runs.
- Ctrl-click compares runs, overlaid in a colour each, or in a column of
  panels per run where colour already tells the series apart.
  `customize_runs` in `plots.yaml` names runs and fixes their colours.
- Clicking a panel enlarges it; the modebar downloads the plot as PNG or SVG
  and the drawn lines as CSV.
- Files are read a run and the plotted series at a time. Polars runs on one
  thread unless `POLARS_MAX_THREADS` is set, which loads files of many runs up
  to ten times faster.

### Removed
- The v1 report CSV input, `lantern.toml` and their options: `--mode`,
  `--config`, `--outdir`, `--init`, `--validate`, `--list-scenarios` and
  `--filter`.
- Percentile bands and representative pathways computed by Lantern, with
  `percentiles.csv` and `representatives.csv`; Horizon writes them into its
  compiled file now.
- The pandas, numpy and kaleido dependencies.

## [1.0.0] - 2026-08-18

Initial public release of Lantern, an open-source visualization tool for
scenario ensembles from the
[Navigate](https://github.com/zerocarbonshipping/navigate-zcs) maritime
transition model.
