# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- What gets an entry: Navigate's CONTRIBUTING.md, Changelog. -->

## [2.0.0] - Unreleased

Lantern 2 is a rewrite: a local web app that plots the Parquet results files
Navigate 1.1 and later write, of one run or many, a Horizon 2 study included,
where Lantern 1 drew PNG plots of a Navigate report CSV. The README describes
it; the entries below are the changes from 1.0.0.

### Added
- `lantern [PATH ...]` opens the viewer in the browser on the results files at
  PATH, a folder loading every `.parquet` below it; files can be added and
  unloaded on the page, and Refresh reloads the configuration and PATH.
- `--plot ID[RUN,...][PANEL]` writes a plot, of each run or of runs together,
  as an interactive HTML page in `plots/`, and `--scale FACTOR` sizes its text
  and panels; `--list` prints the runs and the ids and panels of the plots.
- `--data` writes every row of the files, with a `run` column, as `data.csv`.
- `--version` prints the Lantern version and the results and study schemas it
  reads.
- `plots.yaml` declares the plots: the one in the working folder, else in the
  home folder, else the catalogue Lantern ships with. Lantern prints which it
  reads; `configs/README.md` is its manual.
- The packaged `labels.yaml` and `theme.yaml` name, order and colour the
  series, and `plots.yaml` can override their entries.
- `per: kind.attribute` divides a plot by another series of the run, such as
  expenses per cargo-mile. (#7)
- `{currency}` in a plot's `unit` is the currency of its first series, so the
  catalogue labels money in the run's currency. (#8)
- A Horizon study shows each scenario combination with the median and the 5
  to 95 % band of its samples.
- Ctrl-click compares runs, overlaid in a colour each, or in a column of panels
  per run where colour already tells the series apart; `customize_runs` in
  `plots.yaml` names runs and fixes their colours.
- Clicking a panel enlarges it; a toolbar button shares one y axis across the
  panels, and the modebar downloads the plot as PNG or SVG and its lines as CSV.
- Theme buttons on the page: System, Bright or Dark, kept in the browser.
- A file of a results or study schema Lantern does not read stops with a
  message naming the version and the tool to upgrade, as do a Horizon archive
  and a file that is not a results file. (#9)

### Changed
- `--init` writes the catalogue Lantern ships with into the current folder as
  `plots.yaml`, to edit, where it wrote a starter `lantern.toml`.
- Lantern requires Python 3.13 or newer, as Navigate does.

### Removed
- The report CSV input, `combined_report.csv`: open the results file each
  Navigate run writes, `<deck>.parquet`, or the study file `horizon collect`
  writes.
- `lantern.toml`, `LANTERN_CONFIG` and `--config`: `plots.yaml` declares the
  plots.
- `--mode`: a study shows its median and band. `--outdir`: `--plot` writes into
  `plots/` in the current folder.
- `--list-scenarios` and `--filter`: `--list` prints the runs, and the viewer
  picks them. `--validate`: Lantern checks its YAML files at start.
- Lantern's own percentile bands and representative runs, with
  `percentiles.csv` and `representatives.csv`: Horizon's study file holds them.
- PNG output and the pandas, numpy and kaleido dependencies: `--plot` writes
  HTML, and the viewer downloads PNG.

## [1.0.0] - 2026-08-18

Initial public release of Lantern, an open-source visualization tool for
scenario ensembles from the
[Navigate](https://github.com/zerocarbonshipping/navigate-zcs) maritime
transition model.
