# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- What gets an entry: CONTRIBUTING.md, Changelog. -->

## [2.0.0] - Unreleased

Lantern 2 is a rewrite: a local web app that plots the Parquet results files
Navigate writes, of one run or many, a Horizon study included. The README
describes it. The entries below are the changes since the rewrite was merged
(#5).

### Added
- `per: kind.attribute` divides a plot by another series of the run, such as
  expenses per cargo-mile. (#7)
- A button in a figure's toolbar shares one y axis across its panels, so
  they compare on one scale, and gives each its own again.
- Theme buttons on the page: System, Bright or Dark, kept in the browser.
  Dark recolours the page and the figures' background, text and grid; the
  series keep their colours.
- The repository's `plots.yaml` has WTW emissions by fuel and the trade of
  each fleet, and names the runs of Navigate's reference scenarios.

### Changed
- Lantern requires Python 3.13 or newer, as Navigate does.
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
- A `plots.yaml` that is not a mapping of sections, such as a list, stops
  with an error instead of a traceback, as does a section, plot or layer
  that is not a mapping, and a plot without a title or a series.
