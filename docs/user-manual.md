<!--
SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
SPDX-License-Identifier: CC-BY-4.0
-->

# Lantern User Manual

Lantern is a command-line tool that generates statistical quantile plots (p5/median/p95) from scenario ensemble data. It visualizes uncertainty ranges across scenarios, selects representative pathways, and exports tidy CSV summaries.

---

## Table of Contents

1. [Installation](#installation)
2. [Input Data Format](#input-data-format)
3. [Getting Started](#getting-started)
4. [Configuration](#configuration)
   - [CSV Layout](#csv-layout)
   - [Scenarios](#scenarios)
   - [Metrics](#metrics)
   - [Weights](#weights)
   - [Plot Appearance](#plot-appearance)
   - [Quantile Settings](#quantile-settings)
   - [Representative Pathway Settings](#representative-pathway-settings)
   - [Traces Style](#traces-style)
   - [Performance](#performance)
   - [Output](#output)
   - [Mode-Specific Overrides](#mode-specific-overrides)
5. [CLI Reference](#cli-reference)
6. [Visualization Modes](#visualization-modes)
7. [Representative Pathway Selection](#representative-pathway-selection)
8. [Output Files](#output-files)
9. [Worked Example](#worked-example)
10. [Troubleshooting](#troubleshooting)

---

## Installation

**Requirements:** Python >= 3.12

### Option A -- Editable install (recommended for development)

```bash
git clone <your-repo-url>
cd lantern
pip install -e .
```

### Option B -- Regular install

```bash
git clone <your-repo-url>
cd lantern
pip install .
```

After installation the `lantern` command is available in your terminal. On Windows, if PowerShell blocks the entrypoint, use `python -m lantern.cli` instead.

---

## Input Data Format

Lantern expects a CSV file where columns represent individual scenario samples (runs) and rows contain time-series data for various metrics. The CSV layout is configured via the `[csv_layout]` section, but the default structure is:

| Row   | Content                                                                 |
|-------|-------------------------------------------------------------------------|
| 0     | Sample labels containing scenario keywords (e.g. `ambitious_sample_001`) |
| 2     | Metric headers (e.g. `TotalEquivalentWTW`, `ConsumedEnergy`)            |
| 3     | Subcategory labels for multi-metrics (e.g. `Solar`, `Wind`, `Diesel`)   |
| 5+    | Yearly data -- first column holds year strings, remaining columns hold values |

**Example CSV structure:**

```
,ambitious_sample_001,ambitious_sample_002,...,pledged_sample_001,...
,...,...,...,...,...
,TotalEquivalentWTW,TotalEquivalentWTW,...,ConsumedEnergy,...
,,,...,Solar,...
,...,...,...,...,...
2018,1.5,1.2,...,100,...
2019,1.6,1.3,...,105,...
2020,1.7,1.4,...,110,...
```

Key points:
- Column 0 contains row labels (years in the data rows).
- Columns 1+ contain sample data, grouped by scenario.
- Scenario identification is done by matching keywords from `scenarios.names` against the labels in row 0.

---

## Getting Started

### 1. Generate a starter configuration

If you have a CSV but no config file yet, Lantern can auto-generate one:

```bash
lantern data.csv --init
```

This scans your CSV and creates a `lantern.toml` with detected metrics, scenarios, and default weights. Review and adjust it as needed.

### 2. Validate your configuration

Before plotting, verify that your config matches the CSV:

```bash
lantern data.csv --validate --config lantern.toml
```

This checks that configured metrics exist in the header row, scenarios are found in row 0, and weights are not all zero.

### 3. List scenarios in your data

To see what scenarios are available in the CSV:

```bash
lantern data.csv --list-scenarios
lantern data.csv --list-scenarios --filter ambitious   # filter by substring
```

### 4. Generate plots

```bash
lantern data.csv --config lantern.toml --mode quantiles --outdir output
```

This produces interactive HTML plots and CSV exports in the `output/` directory.

---

## Configuration

Lantern is configured through a TOML file. The config file is resolved in the following priority order:

1. `--config` CLI argument (explicit path)
2. `$LANTERN_CONFIG` environment variable
3. `lantern.toml` in the current working directory
4. Built-in defaults

### CSV Layout

Controls how Lantern interprets the rows of your CSV.

```toml
[csv_layout]
data_start_row  = 5    # First row containing yearly data (0-based)
header_row      = 2    # Row containing metric headers (0-based)
subcategory_row = 3    # Row containing subcategory labels (0-based)
```

### Scenarios

Define the scenario names, display colors, and optional display titles.

```toml
[scenarios]
names = ["ambitious", "pledged", "confirmed", "removed"]

[scenarios.colors]
ambitious = "#6ABF8B"
pledged   = "#4DA6CE"
confirmed = "#D49B2C"
removed   = "#DA6C60"

[scenarios.titles]          # Optional -- display names for plot legends
ambitious = "Ambitious"
pledged   = "Pledged"
confirmed = "Confirmed"
removed   = "Removed"
```

- `names`: Keywords used to match sample labels in row 0 of the CSV.
- `colors`: Hex color codes for each scenario.
- `titles`: Optional human-readable names. If omitted, the scenario key is used.

### Metrics

#### Single metrics

Metrics that have one value per sample per year (no subcategories).

```toml
[metrics.single]
TotalEquivalentWTW          = "emissions"      # CSV header = short key
Expenses                    = "expenses"
IntensityTotalEquivalentWTW = "intensity"
```

The left side is the exact string in the CSV header row. The right side is a short key used in filenames, weights, and output references.

#### Multi metrics

Metrics that are broken down by subcategory (e.g. energy consumed by fuel type).

```toml
[[metrics.multi]]
header    = "ConsumedEnergy"     # Exact string in CSV header row
key       = "consumed_energy"    # Short key for filenames/weights
grid_cols = 3                    # Number of columns in the subplot grid

[[metrics.multi]]
header    = "InstalledPower"
key       = "installed_power"
grid_cols = 2

[[metrics.multi]]
header    = "FuelTypeEnergy"
key       = "fuel_type_energy"
grid_cols = 3
```

#### Skipping subcategories

Exclude specific subcategories from multi-metric plots:

```toml
[metrics.skip_sub]
installed_power  = ["DIESEL", "HYDROGEN"]
fuel_type_energy = ["HYDROGEN"]
```

### Weights

Weights control how the representative pathway is selected. Higher weight means that metric has more influence on which sample is chosen as the representative.

```toml
[weights.single]
emissions = 0.4
expenses  = 0.1
intensity = 0.0       # 0 means this metric is ignored for selection

[weights.multi]
consumed_energy  = 0.0
installed_power  = 0.3
fuel_type_energy = 0.2
```

Notes:
- Weights do not need to sum to 1 -- they are relative.
- Multi-metric weights are split evenly across subcategories present for that metric.
- Setting a weight to 0 excludes that metric from representative selection.

### Plot Appearance

```toml
[plots]
min_row_height       = 400        # Minimum height per subplot row (px)
fixed_height         = 1200       # Fixed height for single-metric plots (px)
paper_bgcolor        = "white"    # Background color of the plot area
plot_bgcolor         = "white"    # Background color of the chart area
show_legend          = true       # Show/hide the legend
legend_orientation   = "h"        # "h" for horizontal, "v" for vertical
legend_x             = 1.0        # Legend x position (0-1)
legend_y             = 1.02       # Legend y position
legend_xanchor       = "right"
legend_yanchor       = "bottom"
margin_top           = 60         # Plot margins (px)
margin_right         = 40
margin_bottom        = 40
margin_left          = 40
y_rangemode          = "tozero"   # Y-axis range mode
traces_tickformat    = "%Y"       # X-axis tick format in traces mode
quarterly_tickformat = "Q%q %Y"   # Tick format for quarterly data
```

### Quantile Settings

```toml
[quantiles]
show_median      = false    # Whether to draw a visible median line
median_line_width = 3.0     # Width of the median line (if shown)
# median_dash    = "solid"  # Optional: dash style for the median line
band_alpha       = 0.18     # Opacity of the p5-p95 shaded band
q_low            = 5        # Lower percentile (default: 5)
q_high           = 95       # Upper percentile (default: 95)
```

### Representative Pathway Settings

```toml
[representatives]
show          = true     # Overlay representative pathway on plots
line_width    = 2.5      # Line width for the representative trace
# dash        = "dash"   # Optional: dash style override
darken_factor = 0.75     # How much to darken the scenario color (0-1)
```

You can also select representatives at multiple percentile targets:

```toml
[[representatives.targets]]
percentile = 50
label      = "representative"
```

### Traces Style

Controls the appearance of faint sampled traces in `traces` mode.

```toml
[traces]
line_width        = 1.0       # Width of individual trace lines
opacity           = 0.25      # Opacity of faint traces
complete_legend   = false     # Show legend entry for every trace
scenario_legend   = true      # Show one legend entry per scenario
per_trace_dashing = false     # Apply different dash styles per trace
dash_cycle        = ["solid", "dash", "dot", "longdash", "dashdot", "longdashdot"]
```

### Performance

```toml
[performance]
max_traces_per_subplot = 200    # Downsample if more traces than this
```

### Output

```toml
[output]
dir = "2_output"    # Default output directory
```

### Mode-Specific Overrides

Override any plot setting for a specific mode using `[mode.<mode>.<section>]`:

```toml
[mode.traces.plots]
margin_top = 80
legend_y   = 1.10

[mode.quantiles.plots]
show_legend = false
```

---

## CLI Reference

```
lantern CSV_PATH [OPTIONS]
```

| Option                  | Description                                             | Default      |
|-------------------------|---------------------------------------------------------|--------------|
| `CSV_PATH`              | Path to the input CSV file (required)                   | --           |
| `--mode {quantiles,traces}` | Visualization mode                                 | `quantiles`  |
| `--config PATH`         | Path to TOML configuration file                         | auto-detect  |
| `--outdir DIR`          | Output directory for plots and CSVs                     | `2_output`   |
| `--list-scenarios`      | List unique scenarios found in the CSV, then exit       | --           |
| `--filter SUBSTRING`    | Filter scenarios by substring (with `--list-scenarios`) | --           |
| `--validate`            | Validate config against CSV and report issues           | --           |
| `--init`                | Auto-generate a starter `lantern.toml` from the CSV     | --           |

**Alternative invocation** (works everywhere, including Windows):

```bash
python -m lantern.cli CSV_PATH [OPTIONS]
```

**Environment variable:**

```bash
export LANTERN_CONFIG=/path/to/lantern.toml
```

---

## Visualization Modes

### Quantiles mode (default)

```bash
lantern data.csv --mode quantiles
```

Generates plots with:
- Shaded bands showing the p5-p95 range for each scenario.
- An optional median line (controlled by `quantiles.show_median`).
- Representative pathway overlay as a dashed, darker line.

This is the recommended mode for clean, publication-ready visualizations.

### Traces mode

```bash
lantern data.csv --mode traces
```

Generates plots with:
- Faint individual traces for every sample in each scenario.
- Quarterly interpolation of time-series data for smoother curves.

Note: Traces mode shows only the raw sample lines. Quantile bands (p5/p95) and the representative pathway overlay are **not** rendered in this mode -- switch to `quantiles` mode for those.

This mode is useful for exploring the full distribution of samples and identifying outliers. For large datasets, tune `performance.max_traces_per_subplot` to limit the number of visible traces.

---

## Representative Pathway Selection

Lantern automatically selects one representative sample per scenario. The selection process works as follows:

1. **Percentile transformation**: All sample data is converted to percentile ranks (0-100), creating a unitless space where different metrics are comparable.
2. **Weighted scoring**: For each sample, a score is calculated as the weighted mean squared error (MSE) from the target percentile (default: 50th, i.e. the median).
3. **Weight distribution**: Single-metric weights are applied directly. Multi-metric weights are split evenly across the subcategories present for that metric.
4. **Selection**: The sample with the lowest weighted MSE is chosen as the representative for each scenario.

The representative pathway is overlaid on all plots as a dashed, darker version of the scenario's color.

You can control this behavior through:
- `[weights.single]` and `[weights.multi]` -- adjust which metrics influence selection.
- `[representatives]` -- toggle visibility and styling of the overlay.
- `[[representatives.targets]]` -- select representatives at percentiles other than the median.

---

## Output Files

After a successful run, Lantern produces the following in the output directory:

### HTML plots

| File pattern                              | Description                              |
|-------------------------------------------|------------------------------------------|
| `<outdir>/<key>.html`                     | Combined view for a single metric        |
| `<outdir>/<scenario>/<key>.html`          | Per-scenario view for a single metric    |
| `<outdir>/<key>_grid.html`               | Combined subplot grid for a multi metric |
| `<outdir>/<scenario>/<key>_grid.html`    | Per-scenario subplot grid                |

Where `<key>` is the short key from your config (e.g. `emissions`, `installed_power`).

### CSV exports

| File                             | Description                                                              |
|----------------------------------|--------------------------------------------------------------------------|
| `<outdir>/representatives.csv`   | Original CSV layout narrowed to the representative columns per scenario  |
| `<outdir>/percentiles.csv`       | Tidy long-format table: `Metric, Scenario, Subcategory, Year, p<q_low>, p50, p<q_high>` (column names reflect `quantiles.q_low`/`q_high` settings, e.g. `p5, p50, p95` at defaults) |

---

## Worked Example

This example walks through a typical workflow from start to finish.

### Step 1: Inspect your data

```bash
lantern combined_report.csv --list-scenarios
```

Output:
```
Scenarios found (4):
  ambitious  (120 samples)
  pledged    (120 samples)
  confirmed  (120 samples)
  removed    (120 samples)
```

### Step 2: Generate a starter config

```bash
lantern combined_report.csv --init
```

This creates `lantern.toml` with auto-detected settings. Open it and review:
- Verify `scenarios.names` matches your expected scenarios.
- Set meaningful colors in `scenarios.colors`.
- Adjust `weights` to reflect which metrics matter most for representative selection.

### Step 3: Validate the config

```bash
lantern combined_report.csv --validate --config lantern.toml
```

Fix any reported issues (missing metrics, unmatched scenarios, etc.).

### Step 4: Generate quantile plots

```bash
lantern combined_report.csv --mode quantiles --config lantern.toml --outdir results
```

### Step 5: Explore with traces (optional)

```bash
lantern combined_report.csv --mode traces --config lantern.toml --outdir results
```

### Step 6: Review outputs

Open the HTML files in a browser. They are interactive Plotly charts that support zooming, panning, and hovering for data values.

Check `results/representatives.csv` to see which samples were chosen, and `results/percentiles.csv` for the computed quantile data.

---

## Troubleshooting

### Windows: entrypoint blocked ("Access is denied")

Use the module invocation:

```powershell
python -m lantern.cli .\combined_report.csv --config .\lantern.toml
```

Or allow scripts for the session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### No plots or empty outputs

- Check console output for warnings like `no columns for '...'`.
- Verify that your CSV header row values match the keys in `metrics.single` and `metrics.multi.header`.
- Verify that scenario keywords from `scenarios.names` appear in the sample labels in row 0.
- Run `--validate` to identify mismatches.

### Large CSVs are slow

- Use `--mode quantiles` instead of `traces` (quantiles mode does not render individual traces).
- Reduce `performance.max_traces_per_subplot` in your config.

### Plots look wrong or have missing data

- Check `csv_layout` settings -- make sure `data_start_row`, `header_row`, and `subcategory_row` point to the correct rows (0-based).
- Verify year values in the first column are 4-digit numbers (e.g. `2018`, not `18`).
- Check for unexpected empty rows or columns in your CSV.

### Config file not found

Lantern searches for the config in this order:
1. `--config` argument
2. `$LANTERN_CONFIG` environment variable
3. `lantern.toml` in the current working directory

If none is found, built-in defaults are used. Use `--config` to specify an explicit path.
