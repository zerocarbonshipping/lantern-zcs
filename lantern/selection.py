# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

import logging

import numpy as np

from . import config
from .percentiles import extract_year_rows, label_matches_scenario, metric_columns, percentile_matrix

logger = logging.getLogger(__name__)


def _manual_rep_label(df, scenario: str, pattern: str):
    """
    Find the first label (row 0) whose text contains both the scenario and the pattern (case-insensitive).
    Returns the full label string or None.
    """
    scen = str(scenario).lower()
    pat = str(pattern).lower()
    labels = []
    for c in range(df.shape[1]):
        lab = str(df.iat[0, c])
        low = lab.lower()
        if scen in low and pat in low:
            labels.append(lab)
    return labels[0] if labels else None


def mse_to_target_in_percentiles(df, rows_idx, cols, target_percentile=50.0):
    if not cols:
        return [], np.array([])
    data = df.iloc[rows_idx, cols].astype(float).values
    P = percentile_matrix(data)
    err = P - target_percentile
    mse = np.nanmean(err * err, axis=0)
    labels = [str(df.iat[0, c]) for c in cols]
    return labels, mse


# Backwards-compatible alias
mse_to_median_in_percentiles = mse_to_target_in_percentiles


def choose_representatives(df, dfv, weights_single, weights_multi, targets=None):
    """Select representative samples per scenario for each target percentile.

    Parameters
    ----------
    targets : list[float] | None
        Percentile targets (e.g. [5.0, 50.0, 95.0]).  Defaults to [50.0].

    Returns
    -------
    dict : {scenario: {percentile: {"sample_label": str, "weighted_score": float, "per_component": dict}}}
    """
    if targets is None:
        targets = [50.0]

    rows_idx, _years = extract_year_rows(dfv)
    result = {}

    # Build multi-metric index of subcategories
    multi_index = {}
    for metric_hdr, m_short, _ in config.MULTI_METRICS:
        cols_all = metric_columns(df, metric_hdr, scenario_key=None)
        if not cols_all:
            multi_index[m_short] = {"subcats": {}}
            continue
        subcats = [str(dfv[config.SUBCAT_ROW, c]) for c in cols_all]
        if m_short in config.SKIP_SUB:
            mask = [s not in config.SKIP_SUB[m_short] for s in subcats]
            cols_all = [c for c, keep in zip(cols_all, mask) if keep]
            subcats = [s for s, keep in zip(subcats, mask) if keep]
        sub_map = {}
        for c, s in zip(cols_all, subcats):
            sub_map.setdefault(s, []).append(c)
        multi_index[m_short] = {"subcats": sub_map}

    for scenario in config.SCENARIOS:
        target_results = {}

        for target_pct in targets:
            all_labels = set()

            # Single metrics
            single_components = {}
            for metric_hdr, short in config.SINGLE_METRICS.items():
                cols = metric_columns(df, metric_hdr, scenario_key=scenario)
                labels, mse = mse_to_target_in_percentiles(df, rows_idx, cols, target_percentile=target_pct)
                single_components[short] = {"labels": labels, "mse": mse, "weight": float(weights_single.get(short, 0.0))}
                all_labels.update(labels)

            # Multi metrics (split weight across subcategories)
            multi_components = {}
            for _metric_hdr, m_short, _ in config.MULTI_METRICS:
                sub_map = multi_index.get(m_short, {}).get("subcats", {})
                subcats = list(sub_map.keys())
                if not subcats:
                    continue
                per_sub_weight = float(weights_multi.get(m_short, 0.0)) / max(len(subcats), 1)
                for sublab in subcats:
                    cols_scens = [c for c in sub_map[sublab] if label_matches_scenario(df.iat[0, c], scenario)]
                    labels, mse = mse_to_target_in_percentiles(df, rows_idx, cols_scens, target_percentile=target_pct)
                    key = f"{m_short}|{sublab}"
                    multi_components[key] = {"labels": labels, "mse": mse, "weight": per_sub_weight}
                    all_labels.update(labels)

            if not all_labels:
                continue

            # Build O(1) label->index dicts for fast lookup
            for comp in single_components.values():
                comp["label_idx"] = {lab: i for i, lab in enumerate(comp["labels"])}
            for comp in multi_components.values():
                comp["label_idx"] = {lab: i for i, lab in enumerate(comp["labels"])}

            scores = {}
            for label in all_labels:
                num = 0.0
                wsum = 0.0
                per_comp = {}
                for short, comp in single_components.items():
                    w = comp["weight"]
                    idx = comp["label_idx"].get(label)
                    if w > 0 and idx is not None:
                        v = float(comp["mse"][idx])
                        per_comp[short] = v
                        num += w * v
                        wsum += w
                    else:
                        per_comp[short] = np.nan
                for key, comp in multi_components.items():
                    w = comp["weight"]
                    idx = comp["label_idx"].get(label)
                    if w > 0 and idx is not None:
                        v = float(comp["mse"][idx])
                        per_comp[key] = v
                        num += w * v
                        wsum += w
                    else:
                        per_comp[key] = np.nan
                if wsum > 0:
                    scores[label] = (num / wsum, per_comp)

            if not scores:
                continue

            best_label, (best_score, per_comp) = min(scores.items(), key=lambda kv: kv[1][0])
            target_results[target_pct] = {"sample_label": best_label, "weighted_score": best_score, "per_component": per_comp}

            # Manual override from config applies to P50 target only
            if target_pct == 50.0:
                manual = config.MANUAL_REPRESENTATIVES.get(scenario)
                if manual:
                    label = _manual_rep_label(df, scenario, manual)
                    if label:
                        logger.debug(f"Manual representative for {scenario}: '{label}' (pattern='{manual}')")
                        target_results[target_pct] = {
                            "sample_label": label,
                            "weighted_score": float("nan"),
                            "per_component": {}
                        }
                    else:
                        logger.warning(
                            f"Manual representative pattern '{manual}' for {scenario} "
                            "did not match any label; keeping automatic selection.")

        if target_results:
            result[scenario] = target_results

    return result
