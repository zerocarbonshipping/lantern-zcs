<!--
SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
SPDX-License-Identifier: CC-BY-4.0
-->

# Lantern

Lantern is a local web app that plots the results of
[Navigate](https://github.com/zerocarbonshipping/navigate-zcs), the
open-source maritime transition model. Every Navigate run writes a Parquet
results file; Lantern opens one or many of them, prepares the plots that
[`plots.yaml`](plots.yaml) declares and serves them as interactive
Plotly figures to the browser. It can also write the same plots as PNG and the
raw rows as CSV without a browser.

It is a small Python package, about 1 200 lines, with a static page of plain
JavaScript and no build step: Python 3.12+, Polars, Plotly, PyYAML and tqdm.

## Install

```bash
pip install lantern-zcs             # the package
pip install 'lantern-zcs[export]'   # plus kaleido, for PNG export
pip install -e '.[dev]'             # a checkout, with ruff and reuse
```

PNG export renders through [kaleido](https://github.com/plotly/Kaleido), which
drives a Chrome instance. The `plotly_get_chrome` command installs one. Depending on the development evironment (WSL) other dependencies might exist.

## Use

```bash
navigate my_deck.nav -d ./assumptions   # writes my_deck.parquet
lantern my_deck.parquet                 # opens the viewer on that run
lantern study/ other.parquet            # every .parquet below study/, and the file
lantern --list e2e.parquet              # the runs, and the ids of the plots with data
lantern --plot fleet_speed e2e.parquet  # that plot of each run: plots/<run>/fleet_speed.png
lantern --plot 'fleet_speed[e2e/none_main,e2e/nzf_main]' e2e.parquet   # the two runs in one figure
lantern --plot 'fleet_speed[][Ferry]' e2e.parquet   # one panel, of each run
lantern --data study/                   # every row of the files as data.csv
```

| Argument | Meaning |
|---|---|
| `PATH ...` | results files, or folders; a folder loads every `.parquet` file in it and below, named by its path in the folder |
| `--plot ID[RUN,...][PANEL]` | no viewer: write one plot as PNG, 1920 by 1080 pixels, as the viewer first opens it: a plot with a view select in its first view. `ID` alone writes it for each run, as `plots/<run>/<id>.png` in the current folder; `ID[RUN,...]` draws the runs together in one figure, as the viewer compares them, into `plots/<id>/<run>+<run>.png`. A second bracket names one panel, by the key `--list` prints or its display name, to draw alone, as the viewer enlarges it, with `_<panel>` added to the file name; `ID[][PANEL]` is that panel of each run. A run is named as in its file, `nzf_main` for `e2e/nzf_main`, or by its full id with `_` for `/` where two files have a run of that name. Repeat it for more; the paths written are printed. An unknown id or run is an error, a plot without data is named and skipped. Quote it where the shell expands `[]`, as zsh does. |
| `--list` | no viewer: print the loaded runs and the id, section, title and panels of every plot with data, for `--plot` |
| `--data` | no viewer: write every row of the files, with a `run` column, as `data.csv` in the current folder. Needs no kaleido. |
| `-h`, `--help` | the arguments |

The switches combine: `--data --plot ID` writes both. Errors, a missing path, a
file that is not a results file, a bad YAML value, a PNG that cannot be
rendered, print `Error: ...` and exit with 1. The viewer listens on
`127.0.0.1:8050`, or a free port when that is taken, and opens the browser.

### The page

- **Runs** are listed in the right column, a plain file as one run and a
  compiled file with its runs under it. Click selects a run; Ctrl-click
  (Cmd-click on a Mac) adds or removes one, to compare. A selected run's
  button takes its colour. A Horizon study's file lists a run per scenario,
  the representative sample, and draws the 5th to 95th percentile over the
  samples as a band behind each line and the median dashed; a stack shows
  the representative alone, as percentiles do not add up.
- **Plots** are listed by section on the left; a plot none of the selected
  runs has data for is greyed out.
- **Views and panels**: a plot with `select_view` shows one node, fuel or
  attribute at a time, chosen in the toolbar. Clicking a panel of a
  multi-panel plot enlarges it; the panel select or Escape goes back.
- **Comparing**: lines of several runs share the panels, a colour per run.
  Stacks, and plots whose series are told apart by colour, get a column of
  panels per run with a shared y axis.
- **Downloads**: the modebar has a camera for PNG, one for SVG and a disk for
  the drawn lines as CSV, a row per run, panel, label and date.
- **Files**: Add files, or drop them on the page, uploads them to the server;
  × unloads one. Refresh reads `plots.yaml` again and reloads the paths
  Lantern was started with from disk, so an edited catalogue or an overwritten
  run shows without a restart. Files added on the page stay.
- The column widths are draggable and kept in the browser. An offline badge
  shows when the server is gone; a restarted server is picked up.

## Configuration

Three YAML files. The catalogue is the user's and travels with a study; the
other two are part of the package.

| File | Where | What it holds | Manual |
|---|---|---|---|
| `plots.yaml` | the folder Lantern is started in, or, if there is none, the home folder; this repository's is [`plots.yaml`](plots.yaml) in its root | the catalogue: every plot's series, layers, panels, views, unit and axis, grouped in sections. `customize_runs` names runs and fixes their colours; `labels` and `theme` override entries of the two files below | [`PLOTS.md`](PLOTS.md) |
| [`lantern/labels.yaml`](lantern/labels.yaml) | the package | the display name and colour name of each label that tells series apart (fuels, fleets, plants, ...); the order of listing is the stacking and panel order | header of the file |
| [`lantern/theme.yaml`](lantern/theme.yaml) | the package | the Center's colours: eight palettes in shades 0 to 8, such as `blue_5`, the palette for labels and runs without a colour, and the figures' font | header of the file |

Without a `plots.yaml` in either place Lantern stops and says so.

The split is deliberate: `plots.yaml` says *what* is plotted and nothing
about looks, apart from the overrides; `labels.yaml` says what the series are
called and in which order and colour name they come; `theme.yaml` says what a
colour name is.

`config.load_config` validates all three at start and on Refresh. It stops
with the file and line when an unquoted value reads as another type, such as
`no`, `on` or `2030`, and with the plot's id on an unknown key, `total`
together with `split_by`, a bad `y_axis` or malformed `variants`.

## Development

```bash
pip install -e '.[dev]'
make lint          # ruff check lantern; reuse lint
lantern PATH       # look at the plots a change touches
```

There is no test suite; CI runs ruff, REUSE, builds the wheel and loads the
repository's catalogue with it. Before a pull request, lint, open results files
and check the plots the change touches, and say in the description how the
rendered plots or exported files differ. Changes to the catalogue or the
labels go in `plots.yaml` in the repository root and `lantern/labels.yaml`
with their headers and
`PLOTS.md` updated; user-visible changes get a line in
[`CHANGELOG.md`](CHANGELOG.md).

A quick check of the loading pipeline without a browser:

```python
from lantern import results
from lantern.config import load_config

loaded = results.load("my_deck.parquet", "my_deck", load_config().plots)
print(loaded.runs, sorted(loaded.plots))
print(loaded.plots["main_fuel_consumed"].head())
```

Pull requests target `dev`; `main` holds releases, which the workflows in
[`.github/workflows`](.github/workflows) publish to PyPI. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the process and
[`CODESTYLE.md`](CODESTYLE.md) for the style: small, no speculative options,
one-line docstrings, guard clauses, specific exceptions with the offending
value.

## Disclaimer

Lantern is an open-source analytical tool intended for research and scenario
analysis of maritime decarbonisation pathways. Its outputs depend on the
model, assumptions, and data selected by the user and are provided for
illustrative and analytical purposes only. They should not be interpreted as
forecasts, benchmarks, recommendations or commercially optimal outcomes, nor
as legal, financial or investment advice. Users are responsible for
selecting appropriate assumptions and for exercising their own independent
judgement when interpreting any outputs.

## License

Copyright 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping.

The `lantern` package and all build and tooling files are licensed under the
[Apache License 2.0](LICENSES/Apache-2.0.txt) (see also [LICENSE](LICENSE));
the documentation under [CC-BY-4.0](LICENSES/CC-BY-4.0.txt). Every file
declares its license through an `SPDX-License-Identifier` header or
[REUSE.toml](REUSE.toml), following the [REUSE specification](https://reuse.software/).
