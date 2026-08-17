# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd


def _parse_quarter_start(s: object) -> pd.Timestamp | None:
    """
    Parse a date-like token (various formats) and return the **quarter start**
    timestamp (e.g., 2024-04-01 for any date in 2024Q2). Returns None if not parseable.
    """
    if s is None:
        return None
    txt = str(s).strip()
    if not txt or txt.lower() in {"nan", "na", "#n/a"}:
        return None
    # Be robust: try exact formats first, then fall back to parser (dayfirst to match EU-style)
    dt = pd.to_datetime(txt, format="%d/%m/%Y %H.%M", errors="coerce")
    if pd.isna(dt):
        dt = pd.to_datetime(txt, errors="coerce", dayfirst=True)
    if pd.isna(dt):
        return None
    # Canonicalize to quarter start
    q = (dt.month - 1) // 3 * 3 + 1
    return pd.Timestamp(year=dt.year, month=q, day=1)


def align_and_interpolate_to_quarters(
    df: pd.DataFrame,
    dfv: np.ndarray,
    row_positions: List[int],
    col_indices: List[int],
) -> Tuple[pd.DatetimeIndex, np.ndarray]:
    """
    Build a **continuous quarterly** DatetimeIndex from the first column of the CSV
    (using rows at `row_positions`) and return:
        (quarters_index, aligned_values)
    where `aligned_values` is shape [len(quarters_index), len(col_indices)],
    created by time-indexed linear interpolation per series.
    """
    # Parse the first column into quarter starts
    colA = [dfv[i, 0] for i in row_positions]
    parsed = pd.Series([_parse_quarter_start(x) for x in colA])
    quarters = pd.DatetimeIndex(sorted(parsed.dropna().unique()))
    if quarters.empty:
        raise ValueError("Could not infer a quarterly index from the first column.")

    out = np.full((len(quarters), len(col_indices)), np.nan, dtype=float)

    # Interpolate each selected column onto the common quarterly grid
    for j_pos, j in enumerate(col_indices):
        # raw values at original timestamps (some rows may be NaT)
        raw_vals = pd.to_numeric(pd.Series([dfv[i, j] for i in row_positions]), errors="coerce")
        s = pd.Series(raw_vals.values, index=parsed.values)   # timestamp -> value
        s = s[s.index.notna()]
        if s.empty:
            continue
        # If duplicate timestamps, average them
        s = s.groupby(level=0).mean().sort_index()
        # Reindex to quarterly grid and time-interpolate
        s_q = s.reindex(quarters)
        s_q = s_q.interpolate(method="time", limit_direction="both")
        out[:, j_pos] = s_q.to_numpy(dtype=float)

    return quarters, out
