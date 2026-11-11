"""Lantern: a browser viewer for Navigate results files."""

from __future__ import annotations

import os

# a load runs thousands of small queries, which one thread does ten times faster than 14; Polars reads this on import,
# so it is set before any module imports Polars
os.environ.setdefault("POLARS_MAX_THREADS", "1")
