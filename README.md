<!--
SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
SPDX-License-Identifier: CC-BY-4.0
-->

# Lantern

Lantern shows the results of [Navigate](https://github.com/zerocarbonshipping/navigate-zcs),
the open-source maritime transition model, as interactive Plotly plots in the
browser. Every Navigate run writes its results to `<deck>.parquet`; Lantern
reads those files.

## Disclaimer

Lantern is an open-source analytical tool intended for research and scenario
analysis of maritime decarbonisation pathways. Its outputs depend on the
model, assumptions, and data selected by the user and are provided for
illustrative and analytical purposes only. They should not be interpreted as
forecasts, benchmarks, recommendations or commercially optimal outcomes, nor
as legal, financial or investment advice. Users are responsible for
selecting appropriate assumptions and for exercising their own independent
judgement when interpreting any outputs.

## Use

```bash
pip install .
navigate my_deck.nav -d ./assumptions     # writes my_deck.parquet
lantern my_deck.parquet                   # opens the viewer
lantern study/                            # every .parquet file in study/ and below
lantern --plots out/ study/               # every plot of every run as SVG and CSV, no viewer
lantern --data rows.csv study/            # the rows of the files as one CSV, no viewer
```

`--plots` writes `out/<run>/<plot>.svg` and `.csv`, one per view of a plot
that has a node select. It renders SVG through kaleido, installed with
`pip install '.[export]'`, which needs Chrome: `plotly_get_chrome` installs
one. `--data` writes every series and date of the files, with a `run`
column, and needs nothing else.

Files can also be added or dropped on the page. Refresh reads `plots.yaml`
and `labels.yaml` again, so an edit shows without a restart, and reloads the
paths Lantern was opened with from disk, e.g. after a new run overwrote them;
it shows the files there now, and files added on the page stay. The loaded
runs are listed in the sidebar,
and the plots show the selected one; Ctrl-click (Cmd-click on a Mac) more runs to compare
them. Lines of several runs share the panels, a colour per run; stacked plots,
and plots that tell series apart by colour, get a column of panels per run with
a shared y axis. Click a panel of a multi-panel plot to enlarge it; Escape or
"All panels" goes back. The plot's modebar has two cameras, one downloading
the plot as PNG and one as SVG, and a disk that downloads the drawn lines as
CSV, a row per run, panel, label and date, in the file's unit.

### Compiled files

A study, such as one run by
[Horizon](https://github.com/zerocarbonshipping/horizon-zcs), compiles its
scenarios into one results file with a run per scenario, each a single
summary: every series has one value per date. Lantern opens a compiled file
like any other, marks it in the sidebar and lists its runs under it, to
select or compare. Each stacked plot also comes as lines, one panel per
stacked series, and is listed after it as "(Stacked)".

Two YAML files in the package configure Lantern:

- [`lantern/plots.yaml`](lantern/plots.yaml) says what is plotted: the series
  of each plot, its panels, units and axes. [`PLOTS.md`](PLOTS.md) is its
  manual.
- [`lantern/labels.yaml`](lantern/labels.yaml) names the labels that tell
  series apart, such as fuels and fleets, gives each a colour name, such as
  `blue_4`, and sets the stacking order.

The colours come from [`theme.yaml`](theme.yaml), the Center's theme, next to
the package in this repository. It gives the hex value of each colour name and
the colours, in turn, of the other labels and of runs compared in one panel;
`customize_runs` in `plots.yaml` names a run for display and fixes its colour. It is not part
of the package: Lantern installed from a package takes Plotly's colours.

Lantern stops with the file and line when a value YAML would read as another
type, such as `no` or `2030`, is not quoted, or a plot has an unknown key.

## Development

```bash
pip install -e ".[dev]"
make lint
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CODESTYLE.md`](CODESTYLE.md).

## License

Copyright 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping.

The `lantern` package and all build and tooling files are licensed under the
[Apache License 2.0](LICENSES/Apache-2.0.txt) (see also [LICENSE](LICENSE));
the documentation under [CC-BY-4.0](LICENSES/CC-BY-4.0.txt). Every file
declares its license through an `SPDX-License-Identifier` header or
[REUSE.toml](REUSE.toml), following the [REUSE specification](https://reuse.software/).
