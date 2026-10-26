<!--
SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
SPDX-License-Identifier: CC-BY-4.0
-->

# The plot catalogue: `plots.yaml`

[`lantern/plots.yaml`](lantern/plots.yaml) lists every plot Lantern shows: which
series of the results it draws, how, and in which panels. Display names, colours
and order of the series are in [`lantern/labels.yaml`](lantern/labels.yaml). Both
are part of the package, so a change takes effect on the next start.

## The results

A Navigate results file is a table with these columns:

| Column | Meaning |
|---|---|
| `kind` | what the row is about: `global`, `fleet`, `vessel`, `producer`, `plant`, `port`, `regulation`, ... |
| `node` | the name of that fleet, plant, port, ...; empty for `global` |
| `attribute` | the quantity, such as `consumed_energy` or `newbuilds` |
| `key1`, `key2` | what the attribute is further split by, such as a fuel type; empty for a quantity without split |
| `date` | the time step |
| `value` | the number |

A plot names its data as **series** `kind.attribute`, for example
`fleet.newbuilds`: every node of that kind, every key. The file's metadata
gives each attribute a unit.

## Layout of the file

```yaml
main:                        # section
  fuel_consumed:             # entry; the plot id is main_fuel_consumed
    title: Fuel consumed
    variants: [lines, stack]
    draw: stack
    label: shore_power
    series:
      - global.consumed_energy
      - global.shore_power_energy
```

Sections such as `main`, `fuel`, `engine` or `fleet` are free names: the key,
capitalised, is the heading in the page's list, and a new section is a new
key with its entries under it. Sections and entries come in the order
written; nothing in Lantern depends on their names. An entry's
id is `<section>_<entry>`; it is what the page asks the server for, so renaming
an entry only changes the id. An entry holds the plot keys and, for a plot
drawn one way, the layer keys directly. A plot whose series are drawn in
different ways, such as a value and its limit, lists its layers:

```yaml
  speed:
    title: Fleet speed
    panels: node
    layers:
      - series: [fleet.minimum_speed, fleet.maximum_speed]
        split_by: attribute
        line: dot
      - series: fleet.actual_speed
        split_by: attribute
```

## Plot keys

| Key | Values | Meaning |
|---|---|---|
| `title` | text | heading of the plot. Required. |
| `unit` | text | y-axis unit. Default: the file's unit of the first series. Give it when `scale`, `cumulative` or `per_gj` changes the unit. |
| `panels` | `node`, `attribute`, `key1`, `key2` | one panel per value of this column, titled by its label |
| `select_view` | `node`, `attribute`, `key1`, `key2` | one view per value of this column, chosen in the select of the toolbar; the plot shows one at a time |
| `y_axis` | `zero` (default), `fit` | whether the y axis starts at zero or fits the data; `fit` for values around zero or a narrow range |
| `variants` | `[lines, stack]` | for a stack, the ways it is listed, in this order. See [Variants](#variants). |
| `layers` | list | the layers, each with the layer keys below |

A plot of one panel and one view leaves `panels` and `select_view` out.

## Layer keys

| Key | Values | Meaning |
|---|---|---|
| `series` | `kind.attribute` or a list | the data. Required. |
| `draw` | `line` (default), `stack`, `area` | lines; areas stacked on each other; an area between zero and the line |
| `split_by` | `key1` (default), `key2`, `node`, `attribute` | the column that tells the series apart; its value is the label of each |
| `total` | `true` | sum all rows of the layer into one series. Excludes `split_by`. |
| `label` | a label | label of the total, or of rows without a `split_by` value. Default: the attribute for a total, `total` for the rows. |
| `scale` | number | the values are multiplied by it: `100` for a share as a percentage, `-1` to draw below zero |
| `line` | `dash`, `dot`, `dashdot` | dashed line, for a target, limit or bound; default solid |
| `cumulative` | `true` | sum a rate over the time steps up to each date, as Navigate's CUMULATIVE report does; set `unit` |
| `per_gj` | `true` | divide a per-ton value by the heating value of its fuel, GJ/t: the fuel in `key1`, or a plant's own fuel; set `unit` |

Within a layer, the rows that share a label (and panel and view) are summed to
one value per date, so `series: fleet.newbuilds` with `split_by: key1` gives
one line per fuel type, summed over the fleets. A date where no row has a value
is left out and the line breaks there.

## Labels

A label is the identity of a series: the value of its `split_by` column, or
the `label` key. The page shows it as the display name from `labels.yaml`,
draws it in the colour given there, and stacks and orders panels in the order
the labels are listed there. A label not listed is shown as written, in the
next palette colour, after the listed ones. So `label: shore_power` in the
example above gives the shore power rows, which have no fuel type, the name,
colour and place of the `shore_power` label.

## Runs

`customize_runs`, the one top-level key of `plots.yaml` that is not a section, gives a
run a display name and a colour by its name: the run within a compiled file,
or the file name of a plain one. An entry is the display name, or a mapping
of `name` and `color`, as in `labels.yaml`; the colour is a colour name of the
theme or a hex value:

```yaml
customize_runs:
  no_regulation: No regulation
  strong_regulation: {name: Strong regulation, color: "#447a7a"}
```

The display name is used in the sidebar, the legend and the panel titles; a
run not listed is shown as named. Runs compared in one panel are told apart
by colour, a listed one by its own, the others in turn from the palette, so a
scenario that appears in every study keeps its colour while the others vary.
A selected run's colour highlights its button in the sidebar. The lines take
the run colours only when runs are overlaid; a single run, or runs tiled in
columns, keep the label colours of `labels.yaml`.

## Variants

A `draw: stack` plot with `variants: [lines, stack]` is listed twice: first as
lines, one panel per label with the stack's `panels` moved to `select_view`,
then as the stack, titled "<title> (Stacked)" with id `<id>_stacked`. The
lines show how each series develops; the stack shows the total and the
shares. Without `variants` the stack is listed once, as written. `variants`
on a plot without a stack layer is an error.

## Panels, views and comparison

`panels` lays the plot out as a grid of panels with a shared y axis; clicking
one enlarges it, the toolbar select or Escape goes back. `select_view` keeps
the plot to one node, fuel or attribute at a time, chosen in the toolbar. Both
accept the same columns, so `panels: key1` with `select_view: node` shows one
port at a time, a panel per fuel.

Comparing runs (Ctrl-click in the sidebar) overlays lines of several runs on
the same panels, a colour per run. A stack, or a plot whose series are told
apart by colour, gets a column of panels per run instead.

## Rules of thumb

- Series that are zero or missing throughout a run are left out, so a plot
  can name series a results file may not have.
- A missing value, such as a limit without bound, is not drawn.
- Text that YAML reads as another type must be quoted: `"%"`, `"no"`, `"on"`,
  `"2030"`. Lantern stops at the line otherwise and says so.
- Unknown keys, `total` together with `split_by`, a `y_axis` other than `zero`
  or `fit`, and malformed `variants` stop Lantern at start with the plot's id.
- Keep an entry to what the title says. A quantity against its limit is one
  plot of two layers; two unrelated quantities are two plots.

## Recipes

One line per fuel type, summed over the fleets, plus the stack:

```yaml
  installed_power:
    title: Installed power
    variants: [lines, stack]
    draw: stack
    series: global.installed_power
```

A value against its constraint, a panel per feed, one producer at a time:

```yaml
  feed_consumption:
    title: Feed consumption
    panels: key1
    select_view: node
    layers:
      - series: producer.feed_mass
        total: true
      - series: producer.feed_constraint
        total: true
        line: dash
```

Additions above and removals below zero:

```yaml
  changes:
    title: Newbuilds and scrapping
    unit: vessels/year
    panels: node
    y_axis: fit
    variants: [lines, stack]
    layers:
      - series: fleet.scrap
        draw: stack
        scale: -1
      - series: fleet.newbuilds
        draw: stack
```

A cost in USD/GJ from a per-ton price, one port at a time:

```yaml
  bunker_price:
    title: Bunker price
    unit: USD/GJ
    select_view: node
    per_gj: true
    series: port.bunker_price
```
