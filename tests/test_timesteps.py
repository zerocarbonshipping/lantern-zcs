# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for quarterly alignment and date parsing in timesteps.py."""

import pandas as pd
import pytest

from lantern.timesteps import _parse_quarter_start, align_and_interpolate_to_quarters
from tests.conftest import build_report_frame


@pytest.mark.unit
class TestParseQuarterStart:
    def test_eu_style_timestamp(self):
        assert _parse_quarter_start("01/01/2025 00.00") == pd.Timestamp("2025-01-01")

    def test_mid_quarter_date_snaps_to_quarter_start(self):
        assert _parse_quarter_start("15/05/2024") == pd.Timestamp("2024-04-01")

    def test_plain_year(self):
        assert _parse_quarter_start("2030") == pd.Timestamp("2030-01-01")

    def test_unparseable_returns_none(self):
        assert _parse_quarter_start("not a date") is None
        assert _parse_quarter_start(None) is None
        assert _parse_quarter_start("nan") is None


@pytest.mark.unit
class TestAlignAndInterpolate:
    def test_interpolates_missing_quarters(self, two_scenario_config):
        df = build_report_frame(
            [("alpha_sample_001", "MetricA", "", [0.0, 100.0, 300.0])],
            [2025, 2025, 2025],
        )
        df.iat[5, 0] = "01/01/2025 00.00"
        df.iat[6, 0] = "01/04/2025 00.00"
        df.iat[7, 0] = "01/10/2025 00.00"

        quarters, values = align_and_interpolate_to_quarters(df, df.values, [5, 6, 7], [1])
        assert list(quarters) == [
            pd.Timestamp("2025-01-01"),
            pd.Timestamp("2025-04-01"),
            pd.Timestamp("2025-10-01"),
        ]
        assert values[:, 0].tolist() == [0.0, 100.0, 300.0]

    def test_raises_without_parseable_dates(self, two_scenario_config):
        df = build_report_frame(
            [("alpha_sample_001", "MetricA", "", [1.0])],
            [2025],
        )
        df.iat[5, 0] = "no date here"
        with pytest.raises(ValueError, match="quarterly index"):
            align_and_interpolate_to_quarters(df, df.values, [5], [1])
