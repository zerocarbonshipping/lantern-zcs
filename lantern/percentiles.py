# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

import numpy as np

from . import config

# Cache for metric_columns() — cleared on config reload via clear_metric_columns_cache()
_metric_columns_cache: dict = {}


def clear_metric_columns_cache():
    """Clear the metric_columns cache. Call after config.configure()."""
    _metric_columns_cache.clear()


def _best_key_for_label(label: object, keys) -> str | None:
    """
    Among 'keys', return the longest entry that appears as a substring
    in 'label' (case-insensitive). Tie-break lexicographically for determinism.
    """
    lab = str(label).lower()
    cand = [k for k in keys if k in lab]
    if not cand:
        return None
    cand.sort(key=lambda s: (len(s), s), reverse=True)
    return cand[0]


def hex_to_rgba(h, alpha):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join([c * 2 for c in h])
    if len(h) != 6:
        return f"rgba(128,128,128,{alpha})"
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def darken_hex(hex_color, factor=0.75):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join([c * 2 for c in h])
    if len(h) != 6:
        return hex_color
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    r = max(0, min(255, int(r * factor)))
    g = max(0, min(255, int(g * factor)))
    b = max(0, min(255, int(b * factor)))
    return f"#{r:02X}{g:02X}{b:02X}"


def get_color(label_or_scenario):
    lower = str(label_or_scenario).lower()

    # 1) Exact key match: e.g., 'ambitious_ru500'
    if lower in config.COLOR_MAP:
        return config.COLOR_MAP[lower]

    # 2) Most-specific substring match across ALL configured color keys
    best_color_key = _best_key_for_label(lower, config.COLOR_MAP.keys())
    if best_color_key:
        return config.COLOR_MAP[best_color_key]

    # 3) Fallback: resolve sub-scenario → main scenario → color
    best_sub = _best_scenario_for_label(lower)
    if best_sub:
        main = config._SUB_TO_MAIN.get(best_sub)
        if main and main in config.COLOR_MAP:
            return config.COLOR_MAP[main]

    return "grey"


def extract_year_rows(df_values):
    """
    Robustly detect time rows by scanning the first column for *any* 4-digit year
    token between 1900 and 2100 (so '01/01/2025 00.00' is accepted).
    """
    rows_idx, years = [], []
    for i in range(config.DATA_START_ROW, df_values.shape[0]):
        val = df_values[i, 0]
        s = str(val) if val is not None else ""
        year = None
        # find any 4-digit year anywhere in the string
        for j in range(len(s) - 3):
            if s[j:j + 4].isdigit():
                y = int(s[j:j + 4])
                if 1900 <= y <= 2100:
                    year = y
                    break
        if year is not None:
            rows_idx.append(i)
            years.append(year)
    return rows_idx, years


def metric_columns(df, metric_header, scenario_key=None):
    cache_key = (metric_header, scenario_key)
    if cache_key in _metric_columns_cache:
        return _metric_columns_cache[cache_key]
    header = df.iloc[config.HEADER_ROW]
    cols = [i for i, v in enumerate(header) if str(v) == metric_header]
    if scenario_key is not None:
        cols = [i for i in cols if label_matches_scenario(df.iat[0, i], scenario_key)]
    _metric_columns_cache[cache_key] = cols
    return cols


def quantiles_np(block_2d, q_low=5, q_high=95):
    if block_2d.size == 0 or block_2d.shape[1] == 0:
        return None, None, None
    qs = np.nanpercentile(block_2d, [q_low, 50, q_high], axis=1)
    return qs[0], qs[1], qs[2]


def percentile_ranks_1d(values):
    arr = np.array(values, dtype=float)
    mask = ~np.isnan(arr)
    if mask.sum() <= 1:
        out = np.full_like(arr, 50.0, dtype=float)
        out[~mask] = np.nan
        return out
    vals = arr[mask]
    order = np.argsort(vals, kind="mergesort")
    ranks0 = np.empty_like(order, dtype=float)
    ranks0[order] = np.arange(len(vals), dtype=float)
    pct = ranks0 / max(len(vals) - 1, 1) * 100.0
    out = np.full_like(arr, np.nan, dtype=float)
    out[mask] = pct
    return out


def percentile_matrix(data_2d):
    """Vectorized percentile ranking across columns for each row."""
    data = np.asarray(data_2d, dtype=float)
    nrows, ncols = data.shape
    if ncols <= 1:
        P = np.full_like(data, 50.0, dtype=float)
        P[np.isnan(data)] = np.nan
        return P
    P = np.empty_like(data, dtype=float)
    for r in range(nrows):
        row = data[r, :]
        mask = ~np.isnan(row)
        n = mask.sum()
        if n <= 1:
            P[r, :] = 50.0
            P[r, ~mask] = np.nan
            continue
        vals = row[mask]
        order = np.argsort(vals, kind="mergesort")
        ranks = np.empty_like(order, dtype=float)
        ranks[order] = np.arange(n, dtype=float)
        pct = ranks / max(n - 1, 1) * 100.0
        P[r, :] = np.nan
        P[r, mask] = pct
    return P


def _best_scenario_for_label(label: object) -> str | None:
    """Return the single best-matching sub-scenario key for a label.
    Longest matching sub-scenario key wins to prefer 'ambitious_ru500' over 'ambitious'."""
    lab = str(label).lower()
    matches = [s for s in config._ALL_SUB_SCENARIOS if s in lab]
    if not matches:
        return None
    # prefer the longest (most specific) match; tie-break lexicographically for determinism
    matches.sort(key=lambda s: (len(s), s), reverse=True)
    return matches[0]


def main_scenario_for_label(label: object) -> str | None:
    """Return the main scenario group that this label belongs to."""
    best_sub = _best_scenario_for_label(label)
    if best_sub is None:
        return None
    return config._SUB_TO_MAIN.get(best_sub)


def label_matches_scenario(label: object, scenario_key: str) -> bool:
    """Exclusive membership: a label belongs to exactly one main scenario."""
    return main_scenario_for_label(label) == str(scenario_key).lower()
