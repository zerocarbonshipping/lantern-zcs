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

Files and folders can also be added or dropped on the page. Several runs are
shown side by side.

Two files configure Lantern, and either can be replaced by a file of the same
name in `~/.config/lantern/`:

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
