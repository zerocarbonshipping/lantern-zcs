# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

import logging

import numpy as np
import pandas as pd

from . import config
from .percentiles import extract_year_rows, label_matches_scenario, metric_columns, quantiles_np

logger = logging.getLogger(__name__)


def export_reps_original_layout(df, reps, out_path):
    chosen = set()
    for target_dict in reps.values():
        for info in target_dict.values():
            chosen.add(info["sample_label"])
    label_row = df.iloc[0]
    keep = [0]
    for j in range(1, df.shape[1]):
        if str(label_row.iat[j]) in chosen:
            keep.append(j)
    df.iloc[:, sorted(set(keep))].to_csv(out_path, index=False, header=False, lineterminator="\n")
    logger.info(f"Wrote representative pathways to {out_path}")


def export_quantiles_tidy(df, dfv, out_path, data_rows=None):
    records = []
    rows_idx, years = extract_year_rows(dfv)
    if data_rows is None:
        data_rows = dfv[rows_idx]

    q_lo = config.QUANTILES_Q_LOW
    q_hi = config.QUANTILES_Q_HIGH
    col_lo = f"p{q_lo:g}"
    col_hi = f"p{q_hi:g}"

    # Single metrics per scenario (tidy)
    for metric_hdr, _short in config.SINGLE_METRICS.items():
        for scen in config.SCENARIOS:
            cols = metric_columns(df, metric_hdr, scenario_key=scen)
            block = data_rows[:, cols].astype(float, copy=False) if cols else np.zeros((0, 0))
            p5, p50, p95 = quantiles_np(block, q_low=q_lo, q_high=q_hi)
            if p5 is None:
                continue
            for y, a, b, c in zip(years, p5, p50, p95):
                records.append({"Metric": metric_hdr, "Scenario": scen, "Subcategory": "", "Year": y,
                                col_lo: a, "p50": b, col_hi: c})

    # Multi metrics per scenario × subcategory
    for metric_hdr, short, _grid_cols in config.MULTI_METRICS:
        cols_all = metric_columns(df, metric_hdr, scenario_key=None)
        if not cols_all:
            continue
        sub_labels_all = dfv[config.SUBCAT_ROW, cols_all].astype(str).tolist()

        for scen in config.SCENARIOS:
            sel_cols = [c for c in cols_all if label_matches_scenario(dfv[0, c], scen)]
            if not sel_cols:
                continue
            labels_for_sel = [sub_labels_all[cols_all.index(c)] for c in sel_cols]
            if short in config.SKIP_SUB:
                filtered = [(lab, c) for lab, c in zip(labels_for_sel, sel_cols) if lab not in config.SKIP_SUB[short]]
                if not filtered:
                    continue
                labels_for_sel, sel_cols = zip(*filtered)
                labels_for_sel = list(labels_for_sel)
                sel_cols = list(sel_cols)

            # group positions by subcategory
            sublab_to_positions = {}
            for pos, _c in enumerate(sel_cols):
                sublab_to_positions.setdefault(labels_for_sel[pos], []).append(pos)

            data_block = data_rows[:, sel_cols].astype(float, copy=False)
            for sublab, pos_list in sublab_to_positions.items():
                block = data_block[:, pos_list]
                p5, p50, p95 = quantiles_np(block, q_low=q_lo, q_high=q_hi)
                if p5 is None:
                    continue
                for y, a, b, c in zip(years, p5, p50, p95):
                    records.append({"Metric": metric_hdr, "Scenario": scen, "Subcategory": sublab, "Year": y,
                                    col_lo: a, "p50": b, col_hi: c})

    if records:
        pd.DataFrame(records).to_csv(out_path, index=False)
        logger.info(f"Wrote percentiles summary to {out_path}")
    else:
        logger.warning("Note: no quantiles summary written (no matching columns).")
