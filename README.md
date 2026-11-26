# Lantern

Lantern is a local web app that plots the results of
[Navigate](https://github.com/zerocarbonshipping/navigate-zcs), the
open-source maritime transition model. Every Navigate run writes a Parquet
results file; Lantern opens one or many of them, prepares the plots that
[`plots.yaml`](lantern/plots.yaml) declares and serves them as interactive
Plotly figures to the browser. It can also write the same plots as HTML pages
and the raw rows as CSV without starting the viewer.


![Fuel consumed by the fleet from 2026 to 2050, stacked by fuel: fuel oil gives way to bio-fuels, blue ammonia and e-fuels](.github/assets/fuelmix_light.png#gh-light-mode-only)
![Fuel consumed by the fleet from 2026 to 2050, stacked by fuel: fuel oil gives way to bio-fuels, blue ammonia and e-fuels](.github/assets/fuelmix_dark.png#gh-dark-mode-only)

## Install

```bash
pip install lantern-zcs
```

## Use

```bash
lantern my_run.parquet          # opens the viewer on that run
lantern study/                  # every .parquet below study/
lantern --data my_run.parquet   # Export plot data to .csv
lantern --list my_run.parquet   # print the runs and ids of the plots with data
lantern --plot 'fleet_speed' e2e.parquet  # generate the fleet speed plot .html
lantern --init                  # write Lantern's plots.yaml here, to edit

# Example Custom Plot Exports
lantern --plot 'fleet_speed[e2e/none_main,e2e/nzf_main]' my_run.parquet   
lantern my_run.parquet \
    --plot 'main_emission_absolute' \
    --plot 'main_fuel_consumed_stacked' \
    --plot 'main_fuel_type_consumed[][METHANE]'
```

| Argument | Meaning |
|---|---|
| `PATH ...` | results files, or folders; a folder loads every `.parquet` file in it and below, named by its path in the folder, but a Horizon archive |
| `--plot ID[RUN,...][PANEL]` | no viewer: write a plot as an interactive HTML page, see [Writing plots](#writing-plots) |
| `--scale FACTOR` | with `--plot`: draw the text, margins and panel height of each page at `FACTOR` times their size, such as `0.8` for a small frame |
| `--list` | no viewer: print the loaded runs and the id, section, title and panels of every plot with data, for `--plot` |
| `--data` | no viewer: write every row of the files, with a `run` column, as `data.csv` in the current folder |
| `--init` | no viewer: write the `plots.yaml` Lantern ships with into the current folder, to edit; one already there is kept, with an error |
| `--version` | print the Lantern version and the results and study schemas it reads |
| `-h`, `--help` | the arguments |

The switches combine: `--data --plot ID` writes both. Errors, a missing path, a
file that is not a results file, a bad YAML value, an unknown plot, run or
panel, print `Error: ...` and exit with 1. So does a file of a results or study
schema Lantern does not read, naming what to upgrade: Navigate's
[contributing guide](https://github.com/zerocarbonshipping/navigate-zcs/blob/dev/CONTRIBUTING.md#versions-and-releases)
says which tool versions which file. The viewer listens on
`127.0.0.1:8050`, or a free port when that is taken, and opens the browser.

### Writing plots

`--plot` saves a plot as an HTML page in `plots/`, as the viewer first shows
it (a plot with views in its first view). Repeat it for more plots; Lantern
prints the paths it wrote.

- `--plot ID`: the plot of each run, `plots/<run>/<ID>.html`.
- `--plot 'ID[RUN,RUN]'`: those runs together in one figure,
  `plots/<ID>/<run>+<run>.html`. Name the runs as `--list` prints them, e.g.
  `e2e/nzf_main`.
- `--plot 'ID[RUN][PANEL]'`: only that panel, enlarged, with `_<PANEL>` added
  to the file name; `ID[][PANEL]` for each run. Name the panel by its key from
  `--list` or by its title.

File names use a run's name within its file, `nzf_main`, or its full id with
`_` for `/` where two files have a run of that name. An unknown plot or run is
an error; a plot without data is skipped, and Lantern says which. The pages
load plotly.js from the internet. Quote the bracket forms in shells that expand
`[]`, such as zsh.

## Configuration

Lantern draws what `plots.yaml` declares. It reads the file from the folder it
is started in, or, if there is none, from the home folder, so a study can carry
its own. With neither it reads the one it ships with,
[`lantern/plots.yaml`](lantern/plots.yaml); `lantern --init` writes a copy of
that into the current folder, to edit. Lantern prints at start which file it
reads. [`configs/README.md`](configs/README.md) is the manual.

The file holds the catalogue: each plot's series, layers, panels, views, unit
and axis, grouped in sections. A series is `kind.attribute`, e.g.
`fleet.newbuilds`. What can be plotted is what the results file holds:
Navigate's reference manual lists every series in that form, with its unit and
keys, under
[Results file: Results](https://zerocarbonshipping.github.io/navigate-zcs/staging/reference_manual/results_file.html#results).

The names, colours and order of the series and the colours and font of the
figures come with the package, in [`lantern/labels.yaml`](lantern/labels.yaml)
and [`lantern/theme.yaml`](lantern/theme.yaml). Leave those as they are;
three keys of `plots.yaml` override their entries instead:

| Key | Overrides |
|---|---|
| `customize_runs` | a run's display name and colour, by its name within its file |
| `labels` | a label's display name and colour, or adds a label; by the label, such as `OIL` or `ferry` |
| `theme` | swatches by colour name, and the palette or the font as a whole |

```yaml
customize_runs:
  basecase_mid_regulation: {name: Mid regulation, color: blue_5}
labels:
  OIL: {color: black_4}
theme:
  font: {family: Arial, weight: 300}
```

A colour is a colour name of the theme, such as `blue_5`, or a hex value; see
[Labels and theme](configs/README.md#labels-and-theme).

Lantern checks the configuration at start and on Refresh and stops at a
mistake with the file and line, the plot or the label; the
[rules of thumb](configs/README.md#rules-of-thumb) list what it checks.


## Contributing

Lantern follows Navigate's
[contributing guide](https://github.com/zerocarbonshipping/navigate-zcs/blob/dev/CONTRIBUTING.md#horizon-and-lantern) and
[code style](https://github.com/zerocarbonshipping/navigate-zcs/blob/dev/CODESTYLE.md): pull requests target `dev`, and
`CHANGELOG.md` records what a user would notice. Set up and check a change with:

```bash
pip install -e ".[dev]"
ruff check lantern tests && ruff format --check lantern tests && mypy && pytest
```

The tests do not look at the plots: open a results file with `lantern PATH`, look at the plots a change
touches, and describe any difference in the pull request.

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

Lantern is licensed under the [Apache License 2.0](LICENSE).
