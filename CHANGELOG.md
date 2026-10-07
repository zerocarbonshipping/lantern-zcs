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
  at PATH; a folder loads every `.parquet` file below it. Files and folders
  can also be added on the page.
- `plots.toml` declares what is plotted and `style.toml` how it looks, the
  Center's colours by default; a file of the same name in `~/.config/lantern/`
  replaces either.

### Removed
- The report CSV input, all command-line options, the HTML and PNG outputs,
  quantile bands and representative selection, and the pandas, numpy,
  kaleido and tqdm dependencies.

## [1.0.0] - 2026-08-18

Initial public release of Lantern, an open-source visualization tool for
scenario ensembles from the
[Navigate](https://github.com/zerocarbonshipping/navigate-zcs) maritime
transition model.
