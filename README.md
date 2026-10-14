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
```

Files can also be added or dropped on the page, and Refresh
reloads the paths Lantern was opened with from disk, e.g. after a new run
overwrote them; it shows the files there now, and files added on the page
stay. A folder holding a compiled results file (see Ensembles) is not
searched below, as its subfolders hold the samples already in it; open a
subfolder itself to see its files. The loaded runs are listed in the sidebar,
and the plots show the selected one; Ctrl-click (Cmd-click on a Mac) more runs to compare
them. Lines of several runs share the panels, a colour per run; stacked plots,
and plots that tell series apart by colour, get a column of panels per run with
a shared y axis. Click a panel of a multi-panel plot to enlarge it; Escape or
"All panels" goes back.

### Ensembles

An uncertainty study, such as one run by
[Horizon](https://github.com/zerocarbonshipping/horizon-zcs), writes one
results file per sample, and compiles them into one file with a run per
scenario and its samples. Lantern opens a compiled file like any other and
draws an ensemble's lines and areas as the median of its samples with a band
from the 5th to the 95th percentile and a dotted line of its representative
sample. Stacked plots show the representative sample, as medians and
percentiles do not add up. Each stacked plot also comes as lines, one panel per
stacked series with its band, and is listed after it as "(Stacked)". A sample
without a series counts it as zero, since Navigate leaves out series that are
negligible throughout. The sidebar marks a compiled file and lists its runs,
each with its number of samples, to select or compare; a run's tooltip names
its representative sample.

The representative sample is the one closest to the median throughout. At
every date, the series of each plot with a `weight` in `plots.toml` rank the
samples as percentiles; a sample scores its mean squared distance from the
50th percentile, averaged over each plot's series and weighted over the plots,
and the lowest score wins. By default the weights are those of Lantern 1:
emissions 0.4, installed power 0.3, fuel consumed by fuel type 0.2 and
expenses 0.1.

Two files in the package configure Lantern:

- [`lantern/plots.toml`](lantern/plots.toml) says what is plotted: the series
  of each plot, display names, units and axes. Its header lists the keys.
- [`lantern/style.toml`](lantern/style.toml) says how it looks: the colours
  (the Center's palette by default) and chart settings.

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
