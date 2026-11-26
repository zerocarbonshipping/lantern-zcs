# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- What gets an entry: Navigate's CONTRIBUTING.md, Changelog. -->

## [2.0.0] - 2026-11-30

Reads results schema 1 and study schema 1.

Lantern 2 is a rewrite: a local web app that plots the Parquet results files
Navigate writes, of one run or many, a Horizon study included. The README
describes it. The entries below are the changes since the rewrite was merged
(#5).

### Added
- `--scale FACTOR` draws the pages `--plot` writes with their text,
  margins and panel height at that factor, such as `0.8` for a small frame.
- `--version` prints the Lantern version and the results and study schemas
  it reads.
- Lantern ships with its plot catalogue, `lantern/plots.yaml` in the
  repository, formerly `configs/plots.yaml`, and reads it where neither the
  working folder nor the home folder has a `plots.yaml`; it used to stop.
- `--init` writes a copy of that catalogue into the current folder, to edit;
  at start Lantern prints which `plots.yaml` it reads.
- `per: kind.attribute` divides a plot by another series of the run, such as
  expenses per cargo-mile. (#7)
- `{currency}` in a plot's `unit` is the currency of its first series. The
  catalogue's plots that set a unit in USD use it, so they label a run in
  another currency in that currency. (#8)
- A button in a figure's toolbar shares one y axis across its panels, so
  they compare on one scale, and gives each its own again.
- Theme buttons on the page: System, Bright or Dark, kept in the browser.
  Dark recolours the page and the figures' background, text and grid; the
  series keep their colours.
- The repository's `plots.yaml` has WTW emissions by gas and the trade of
  each fleet, and names the runs of Navigate's reference scenarios.

### Changed
- A results file of a schema version Lantern does not read stops with a
  message naming the version and what to upgrade; it opened without units
  or heating values. (#9)
- A Horizon study file of a study schema Lantern does not read stops the same
  way, and both messages name the Navigate, Horizon and Lantern that wrote
  and read the file.
- Lantern requires Python 3.13 or newer, as Navigate does.
- Hovered values show 3 significant figures with thousands grouped, such as
  12,300,000,000 or 0.0123; the CSV downloads keep every digit.
- The oil labels, oil, fuel oil, HFO and crude oil, are lighter: `black_5`
  in place of `black_7`; the LPG fuel type moves to `black_4`, as the LPG
  fuel has.
- The WTW emissions and intensity are `black_5` in place of `black_8`, as
  oil is; supply, produced, constraints, non-compliance and thresholds
  are `black_6` in place of `black_8`.
- `--plot` writes interactive HTML pages instead of PNG; the `export` extra
  and kaleido are no longer needed.
- A colour in `labels.yaml`, `customize_runs` or the theme's palette must be
  a colour name of the theme or a hex value, and a swatch a hex value;
  Lantern stops with an error where an unknown name used to fall back to the
  palette. (#6)
- In the repository's `plots.yaml`, the fleet, vessel and plant plots of
  several lines, and the feed consumption, show one fleet, vessel, plant or
  feed at a time, chosen in the view select, instead of a panel each.

### Fixed
- A Horizon archive, which holds every sample of a study, stops with a
  message instead of plotting the sum of its samples, and a folder leaves it
  out.
- A results file whose dates or values are of another type stops with a
  message instead of a traceback.
- A `plots.yaml` that is not a mapping of sections, such as a list, stops
  with an error instead of a traceback, as does a section, plot or layer
  that is not a mapping, and a plot without a title or a series.
