# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Shared fixtures: config isolation and a builder for report-shaped frames."""

from pathlib import Path

import pandas as pd
import pytest

from lantern import config

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"


@pytest.fixture(autouse=True)
def _isolated_config(monkeypatch):
    """Keep module-level config state deterministic across tests.

    Clears LANTERN_CONFIG so the machine environment cannot leak in, and
    rebinds the built-in defaults after each test since config state lives
    in module globals.
    """
    monkeypatch.delenv("LANTERN_CONFIG", raising=False)
    yield
    monkeypatch.chdir(REPO_ROOT)
    config.configure(None)


def build_report_frame(columns, years):
    """Build a DataFrame shaped like a combined Navigate report.

    Parameters
    ----------
    columns : list of (label, metric_header, subcategory, values) tuples,
        one per data column; values must align with *years*.
    years : list of int years for the first column of the data rows.
    """
    label_row = [""] + [c[0] for c in columns]
    header_row = [""] + [c[1] for c in columns]
    subcat_row = [""] + [c[2] for c in columns]
    blank = [""] * len(label_row)

    rows = [label_row, blank, header_row, subcat_row, blank]
    for i, year in enumerate(years):
        rows.append([str(year)] + [c[3][i] for c in columns])
    return pd.DataFrame(rows)


@pytest.fixture
def two_scenario_config(tmp_path):
    """Configure lantern for a minimal two-scenario, one-metric dataset."""
    toml = tmp_path / "lantern.toml"
    toml.write_text(
        "\n".join(
            [
                "[scenarios]",
                'names = ["alpha", "beta"]',
                "[scenarios.colors]",
                'alpha = "#447a7a"',
                'beta = "#68a4c2"',
                "[metrics.single]",
                'MetricA = "a"',
                "[metrics.multi]",
                "[weights.single]",
                "a = 1.0",
                "[weights.multi]",
            ]
        )
    )
    config.configure(toml)
    return toml
