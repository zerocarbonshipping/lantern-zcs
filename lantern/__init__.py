# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Lantern: a browser viewer for Navigate results files."""

import os

# loading runs thousands of small queries, and Polars splits each over every core, waking its threads takes longer than
# the work: a 20-run file loads about ten times faster on one thread than on 14. Polars reads the setting once, on
# import, so it is set here, before any module imports Polars; a value set already wins
os.environ.setdefault("POLARS_MAX_THREADS", "1")
