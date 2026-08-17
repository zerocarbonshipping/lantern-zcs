# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

import argparse
import logging
import time
import warnings
from pathlib import Path

import pandas as pd
from pandas.errors import DtypeWarning
from tqdm import tqdm

from . import config
from .export import export_quantiles_tidy, export_reps_original_layout
from .logging import setup_logging
from .percentiles import extract_year_rows
from .plotting import plot_multi_metric, plot_single_metric
from .selection import choose_representatives

warnings.simplefilter("ignore", category=DtypeWarning)
setup_logging()
logger = logging.getLogger(__name__)


def list_scenarios(csv_path: Path, filter_str: str | None = None) -> None:
    """Extract and print unique scenario identifiers from CSV row-0 labels."""
    import re
    from collections import Counter

    df = pd.read_csv(csv_path, header=None, low_memory=False)
    labels = df.iloc[0, 1:]  # skip column 0 (time)

    # Strip sample identifiers: _sample_NNN at end of label
    strip_re = re.compile(r"_sample_\d+$", re.IGNORECASE)
    scenarios = []
    for label in labels:
        if pd.isna(label):
            continue
        clean = strip_re.sub("", str(label).strip()).lower()
        if filter_str and filter_str.lower() not in clean:
            continue
        scenarios.append(clean)

    counts = Counter(scenarios)
    print("\nScenario identifiers found:")
    print("-" * 50)
    for name in sorted(counts):
        print(f"  {name:<40} ({counts[name]} samples)")
    print("-" * 50)
    print(f"  {len(counts)} unique scenario(s)\n")


def validate_config(csv_path: Path) -> None:
    """Check TOML config against CSV structure and report issues."""
    from .percentiles import label_matches_scenario, metric_columns

    df = pd.read_csv(csv_path, header=None, low_memory=False)
    header_row = df.iloc[config.HEADER_ROW]
    available_headers = sorted(set(str(v) for v in header_row if pd.notna(v) and str(v).strip()))

    issues = []
    ok_items = []

    # Check single metrics
    for metric_hdr, short in config.SINGLE_METRICS.items():
        cols = metric_columns(df, metric_hdr)
        if cols:
            ok_items.append(f"Single metric '{metric_hdr}' ({short}): {len(cols)} columns")
        else:
            close = [h for h in available_headers if metric_hdr.lower() in h.lower() or h.lower() in metric_hdr.lower()]
            hint = f" Did you mean: {close}?" if close else f" Available: {available_headers[:10]}"
            issues.append(f"Single metric '{metric_hdr}' not found in header row {config.HEADER_ROW}.{hint}")

    # Check multi metrics
    for metric_hdr, short, _grid_cols in config.MULTI_METRICS:
        cols = metric_columns(df, metric_hdr)
        if cols:
            ok_items.append(f"Multi metric '{metric_hdr}' ({short}): {len(cols)} columns")
        else:
            close = [h for h in available_headers if metric_hdr.lower() in h.lower() or h.lower() in metric_hdr.lower()]
            hint = f" Did you mean: {close}?" if close else f" Available: {available_headers[:10]}"
            issues.append(f"Multi metric '{metric_hdr}' not found in header row {config.HEADER_ROW}.{hint}")

    # Check scenarios
    labels_row0 = [str(df.iat[0, c]).lower() for c in range(1, df.shape[1]) if pd.notna(df.iat[0, c])]
    for scenario in config.SCENARIOS:
        matches = [lab for lab in labels_row0 if label_matches_scenario(lab, scenario)]
        if matches:
            ok_items.append(f"Scenario '{scenario}': {len(matches)} samples")
        else:
            issues.append(f"Scenario '{scenario}' matched 0 samples in row 0 labels.")

    # Check weights
    total_weight = sum(config.WEIGHTS_SINGLE.values()) + sum(config.WEIGHTS_MULTI.values())
    if total_weight == 0:
        issues.append("All weights are zero — representative selection will fail.")

    # Report
    print("\n=== Lantern Config Validation ===\n")
    if ok_items:
        print("OK:")
        for item in ok_items:
            print(f"  + {item}")
    if issues:
        print("\nISSUES:")
        for issue in issues:
            print(f"  ! {issue}")
    else:
        print("\nNo issues found.")
    print()


def generate_init_config(csv_path: Path) -> None:
    """Generate a starter lantern.toml by introspecting CSV structure."""
    import re

    df = pd.read_csv(csv_path, header=None, low_memory=False)
    nrows, ncols = df.shape

    # Auto-detect header row (first row with mostly non-numeric, non-empty strings)
    header_row = 2  # default
    for r in range(min(10, nrows)):
        row_vals = [str(v).strip() for v in df.iloc[r, 1:] if pd.notna(v)]
        if not row_vals:
            continue
        numeric_count = sum(1 for v in row_vals if v.replace('.', '', 1).replace('-', '', 1).isdigit())
        if len(row_vals) > 0 and numeric_count / len(row_vals) < 0.3:
            header_row = r
            break

    # Auto-detect data start row (first row where col 0 looks like a year or date)
    data_start_row = 5
    year_re = re.compile(r'\b(19|20)\d{2}\b')
    for r in range(header_row + 1, min(20, nrows)):
        val = str(df.iat[r, 0]) if pd.notna(df.iat[r, 0]) else ""
        if year_re.search(val):
            data_start_row = r
            break

    # Subcategory row: typically header_row + 1
    subcat_row = header_row + 1

    # Extract unique metric headers
    headers = sorted(set(
        str(v) for v in df.iloc[header_row, 1:]
        if pd.notna(v) and str(v).strip()
    ))

    # Extract scenarios from row 0
    strip_re = re.compile(r"_sample_\d+$", re.IGNORECASE)
    scenario_names = []
    for label in df.iloc[0, 1:]:
        if pd.isna(label):
            continue
        clean = strip_re.sub("", str(label).strip()).lower()
        scenario_names.append(clean)

    unique_scenarios = sorted(set(scenario_names))

    # Subcategories per metric header
    subcats_per_header = {}
    for hdr in headers:
        cols = [i for i, v in enumerate(df.iloc[header_row]) if str(v) == hdr]
        subcats = sorted(set(str(df.iat[subcat_row, c]) for c in cols if pd.notna(df.iat[subcat_row, c])))
        if subcats and subcats != ["nan"]:
            subcats_per_header[hdr] = subcats

    # Default colors
    default_colors = ["#6ABF8B", "#4DA6CE", "#D49B2C", "#DA6C60", "#9B59B6", "#1ABC9C", "#E74C3C", "#3498DB"]

    # Write TOML
    out = Path("lantern.toml")
    lines = [
        "# Generated by: lantern --init",
        f"# Source CSV: {csv_path.name} ({ncols} columns, {nrows} rows)",
        "",
        "[csv_layout]",
        f"header_row = {header_row}",
        f"subcategory_row = {subcat_row}",
        f"data_start_row = {data_start_row}",
        "",
        "[scenarios]",
        f"names = {unique_scenarios}",
        "",
        "[scenarios.colors]",
    ]
    for i, s in enumerate(unique_scenarios):
        color = default_colors[i % len(default_colors)]
        lines.append(f'{s} = "{color}"')

    # Classify metrics: single (no subcategories) vs multi (has subcategories)
    single_metrics = {}
    multi_metrics = []
    for hdr in headers:
        key = re.sub(r'[^a-z0-9]+', '_', hdr.lower()).strip('_')
        if hdr in subcats_per_header and len(subcats_per_header[hdr]) > 1:
            multi_metrics.append((hdr, key, subcats_per_header[hdr]))
        else:
            single_metrics[hdr] = key

    lines += ["", "[metrics.single]"]
    for hdr, key in single_metrics.items():
        lines.append(f'{hdr} = "{key}"')

    for hdr, key, subcats in multi_metrics:
        lines += [
            "",
            "[[metrics.multi]]",
            f'header = "{hdr}"',
            f'key = "{key}"',
            f"grid_cols = {min(3, len(subcats))}",
            f"# subcategories: {subcats}",
        ]

    lines += [
        "",
        "[weights.single]",
        "# Set weights > 0 for metrics that matter for representative selection",
    ]
    for _hdr, key in single_metrics.items():
        lines.append(f"{key} = 0.0")

    lines += ["", "[weights.multi]"]
    for _hdr, key, _ in multi_metrics:
        lines.append(f"{key} = 0.0")

    lines += ["", "[output]", 'dir = "2_output"', ""]

    out.write_text("\n".join(lines) + "\n")
    print(f"\nGenerated {out} with {len(single_metrics)} single metric(s), "
          f"{len(multi_metrics)} multi metric(s), {len(unique_scenarios)} scenario(s).")
    print("Edit weights, colors, and metric selections to customize.\n")


def main():
    parser = argparse.ArgumentParser(description="Lantern: plots + representative selection")
    parser.add_argument("csv_path", help="Path to combined_report.csv")

    # NEW: config path (optional)
    parser.add_argument("--config", help="Path to lantern.toml (overrides defaults/env/search)")
    parser.add_argument("--mode", choices=["traces", "quantiles"], default="quantiles",
                        help="Show faint raw traces (sampled) + bands, or just bands.")
    # Output directory
    parser.add_argument("--outdir", default=None, help="Output directory (default: 2_output)")
    # Discovery
    parser.add_argument("--list-scenarios", action="store_true",
                        help="List unique scenario identifiers from CSV and exit")
    parser.add_argument("--filter", type=str, default=None,
                        help="Filter listed scenarios by substring (case-insensitive)")
    parser.add_argument("--validate", action="store_true",
                        help="Validate config against CSV and report issues without generating plots")
    parser.add_argument("--init", action="store_true",
                        help="Generate a starter lantern.toml from the CSV structure")

    args = parser.parse_args()

    # NEW: apply config ASAP so constants reflect the chosen TOML
    config.configure(args.config, mode=args.mode)

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        logger.error(f"Error: '{csv_path}' not found.")
        return

    if args.list_scenarios:
        list_scenarios(csv_path, args.filter)
        return

    if args.validate:
        validate_config(csv_path)
        return

    if args.init:
        generate_init_config(csv_path)
        return

    t0 = time.time()
    skipped_metrics = []
    plot_count = 0

    df = pd.read_csv(csv_path, header=None, low_memory=False)
    dfv = df.values
    outdir = Path(args.outdir) if args.outdir else config.OUTPUT_DIR
    outdir.mkdir(parents=True, exist_ok=True)

    rows_idx, years = extract_year_rows(dfv)

    # Pre-slice data rows once (avoids repeated dfv[rows_idx] copies)
    data_rows = dfv[rows_idx]

    # Choose representatives first for overlay
    logger.info("=== Choosing representatives (weighted, unitless) ===")
    weights_single = dict(config.WEIGHTS_SINGLE)
    weights_multi = dict(config.WEIGHTS_MULTI)
    targets = [t.percentile for t in config.REP_TARGETS]
    reps = choose_representatives(df, dfv, weights_single, weights_multi, targets=targets)
    for scenario, target_dict in reps.items():
        for pct, info in sorted(target_dict.items()):
            logger.info(f"P{pct:g} representative for {scenario}: \t '{info['sample_label']}'")

    # Plot single metrics
    total_metrics = len(config.SINGLE_METRICS) + len(config.MULTI_METRICS)
    pbar = tqdm(total=total_metrics, desc="Plotting metrics", unit="metric")
    for metric_hdr, short in config.SINGLE_METRICS.items():
        pbar.set_postfix_str(short)
        result = plot_single_metric(df, dfv, years, rows_idx, metric_hdr, short, mode=args.mode,
                                    reps=reps, outdir=outdir, data_rows=data_rows)
        if result is False:
            skipped_metrics.append(metric_hdr)
        else:
            plot_count += 1 + len(config.SCENARIOS)  # combined + per-scenario
        pbar.update(1)

    # Plot multi metrics
    for metric_hdr, short, grid_cols in config.MULTI_METRICS:
        pbar.set_postfix_str(short)
        result = plot_multi_metric(df, dfv, years, rows_idx, metric_hdr, short, grid_cols,
                                   mode=args.mode, reps=reps, outdir=outdir, data_rows=data_rows)
        if result is False:
            skipped_metrics.append(metric_hdr)
        else:
            plot_count += 1 + len(config.SCENARIOS)
        pbar.update(1)
    pbar.close()

    # Exports .csv files
    export_reps_original_layout(df, reps, outdir / "representatives.csv")
    export_quantiles_tidy(df, dfv, outdir / "percentiles.csv", data_rows=data_rows)

    # Execution summary
    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s — {plot_count} plots, 2 CSV exports to {outdir}/")
    if skipped_metrics:
        print(f"  Skipped {len(skipped_metrics)} metric(s) (no matching columns): {', '.join(skipped_metrics)}")
