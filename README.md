<!--
SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
SPDX-License-Identifier: CC-BY-4.0
-->

# Lantern

[![CI](https://github.com/zerocarbonshipping/lantern-zcs/actions/workflows/ci.yml/badge.svg)](https://github.com/zerocarbonshipping/lantern-zcs/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSES/Apache-2.0.txt)

Lantern visualizes scenario ensembles from
[Navigate](https://github.com/zerocarbonshipping/navigate-zcs), the
open-source maritime transition model. Given a combined report CSV — for
example the output of an uncertainty study run with
[Horizon](https://github.com/zerocarbonshipping/horizon-zcs) — it generates
quantile plots (p5 / median / p95 bands), selects a representative pathway
per scenario using a weighted percentile-space score, and exports tidy CSVs
of percentiles and representatives.

Lantern is a companion to Navigate: it post-processes Navigate ensemble
outputs and expects their report layout. It runs on any CSV with the same
structure, but it does not produce simulation data itself.

## Disclaimer

Lantern is an open-source analytical tool intended for research and scenario
analysis of maritime decarbonisation pathways. Its outputs depend on the
model, assumptions, and data selected by the user and are provided for
illustrative and analytical purposes only. They should not be interpreted as
forecasts, benchmarks, recommendations or commercially optimal outcomes, nor
as legal, financial or investment advice. Users are responsible for
selecting appropriate assumptions and for exercising their own independent
judgement when interpreting any outputs.

## Requirements

- Python >= 3.12
- A combined Navigate report CSV (one column per sample; see
  [CSV expectations](#csv-expectations))

## Installation

```bash
pip install .
```

For development with lint and test tools:

```bash
pip install -e ".[dev]"
```

On Windows, if PowerShell blocks entrypoint shims, use
`python -m lantern.cli` instead of `lantern`.

## Quick start

The bundled example runs on a small synthetic report:

```bash
cd examples
lantern report.csv --config lantern.toml --outdir output
```

This writes interactive HTML plots plus `percentiles.csv` and
`representatives.csv` to `output/`. See
[`examples/README.md`](examples/README.md) for a walkthrough.

For your own data:

```bash
# Inspect what the CSV contains
lantern report.csv --list-scenarios

# Generate a starter config from the CSV structure
lantern report.csv --init

# Check the config against the CSV
lantern report.csv --validate

# Render
lantern report.csv --mode quantiles --outdir 2_output
```

The config is discovered from `--config`, the `LANTERN_CONFIG` environment
variable, or `lantern.toml` in the current directory, in that order;
built-in defaults apply otherwise.

## CSV expectations

- **Row 0**: sample labels containing scenario keywords, so columns can be
  grouped per scenario
- **Row 2**: metric headers used to find columns (e.g. `TotalEquivalentWTW`,
  `ConsumedEnergy`)
- **Row 3**: subcategory labels for multi-metrics
- **Row 5+**: yearly data; the first column holds the years

All row indices are configurable via `[csv_layout]` in `lantern.toml`.

## Command-line options

```bash
lantern CSV_PATH [--mode {quantiles,traces}] [--config PATH] [--outdir DIR]
```

| Flag | Description |
|------|-------------|
| `--mode quantiles` | Percentile bands with representative overlay (default). |
| `--mode traces` | Faint raw sample traces, no bands or representative overlay. |
| `--config PATH` | Path to `lantern.toml` (overrides env var and CWD search). |
| `--outdir DIR` | Output directory (default `2_output`). |
| `--init` | Generate a starter `lantern.toml` from the CSV structure. |
| `--validate` | Validate the config against the CSV and report issues. |
| `--list-scenarios` | List unique scenarios found in the CSV, then exit. |
| `--filter SUBSTRING` | Filter scenarios by substring (with `--list-scenarios`). |

## Outputs

- `<outdir>/<short>.html` — single-metric combined view; per-scenario copies
  in `<outdir>/<scenario>/`
- `<outdir>/<short>_grid.html` — multi-metric subplot grid, likewise
- `<outdir>/representatives.csv` — the chosen representative columns in the
  original CSV layout
- `<outdir>/percentiles.csv` — tidy long table of the configured quantiles
  per metric, scenario, subcategory, and year

`<short>` is the short key assigned to each metric in the config
(e.g. `emissions`, `installed_power`).

## Documentation

- [`docs/user-manual.md`](docs/user-manual.md) — the full guide:
  configuration reference, visualization modes, representative-pathway
  selection, worked example, troubleshooting
- [Navigate documentation](https://zerocarbonshipping.github.io/navigate-zcs/)
  — the simulation model that produces the input data

## Testing

```bash
pip install -e ".[dev]"
pytest
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for contribution guidelines and
[`CODESTYLE.md`](CODESTYLE.md) for coding conventions.

## License

Copyright 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping.

Lantern is licensed under two licenses, depending on the type of content:

- The software — the `lantern` package, tests, and all build and tooling
  files — is licensed under the
  [Apache License 2.0](LICENSES/Apache-2.0.txt) (see also the root
  [LICENSE](LICENSE) file).
- The documentation and examples are licensed under
  [Creative Commons Attribution 4.0 International](LICENSES/CC-BY-4.0.txt)
  (CC-BY-4.0).

Every file declares its license through an `SPDX-License-Identifier` header
or through the metadata in [REUSE.toml](REUSE.toml), following the
[REUSE specification](https://reuse.software/). The full license texts are
in the [LICENSES](LICENSES/) directory.
