# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the quantile math and CSV-shape helpers in percentiles.py."""

import numpy as np
import pytest

from lantern import config
from lantern.percentiles import (
    _best_key_for_label,
    darken_hex,
    extract_year_rows,
    hex_to_rgba,
    metric_columns,
    percentile_matrix,
    percentile_ranks_1d,
    quantiles_np,
)
from tests.conftest import build_report_frame


@pytest.mark.unit
class TestColorHelpers:
    def test_hex_to_rgba_expands_shorthand(self):
        assert hex_to_rgba("#fff", 0.5) == "rgba(255,255,255,0.5)"

    def test_hex_to_rgba_full(self):
        assert hex_to_rgba("#447a7a", 1.0) == "rgba(68,122,122,1.0)"

    def test_hex_to_rgba_invalid_falls_back_to_grey(self):
        assert hex_to_rgba("#12345", 0.3) == "rgba(128,128,128,0.3)"

    def test_darken_hex(self):
        assert darken_hex("#ffffff", 0.5) == "#7F7F7F"

    def test_darken_hex_invalid_returned_unchanged(self):
        assert darken_hex("#12345", 0.5) == "#12345"


@pytest.mark.unit
class TestQuantiles:
    def test_quantiles_np_known_values(self):
        block = np.array([[1.0, 2.0, 3.0], [10.0, 20.0, 30.0]])
        p_low, p_med, p_high = quantiles_np(block, q_low=0, q_high=100)
        assert p_low.tolist() == [1.0, 10.0]
        assert p_med.tolist() == [2.0, 20.0]
        assert p_high.tolist() == [3.0, 30.0]

    def test_quantiles_np_empty_block(self):
        assert quantiles_np(np.zeros((0, 0))) == (None, None, None)

    def test_quantiles_np_ignores_nan(self):
        block = np.array([[1.0, np.nan, 3.0]])
        _, p_med, _ = quantiles_np(block)
        assert p_med[0] == 2.0


@pytest.mark.unit
class TestPercentileRanks:
    def test_ranks_span_zero_to_hundred(self):
        assert percentile_ranks_1d([10, 20, 30]).tolist() == [0.0, 50.0, 100.0]

    def test_single_value_gets_fifty(self):
        assert percentile_ranks_1d([42.0]).tolist() == [50.0]

    def test_nan_stays_nan(self):
        out = percentile_ranks_1d([10.0, np.nan, 30.0])
        assert np.isnan(out[1])
        assert out[0] == 0.0 and out[2] == 100.0

    def test_matrix_ranks_rows_independently(self):
        data = np.array([[1.0, 2.0, 3.0], [30.0, 20.0, 10.0]])
        P = percentile_matrix(data)
        assert P[0].tolist() == [0.0, 50.0, 100.0]
        assert P[1].tolist() == [100.0, 50.0, 0.0]

    def test_matrix_single_column_is_fifty(self):
        P = percentile_matrix(np.array([[5.0], [7.0]]))
        assert P.tolist() == [[50.0], [50.0]]


@pytest.mark.unit
class TestBestKeyForLabel:
    def test_prefers_longest_match(self):
        keys = ["ambitious", "ambitious_ru500"]
        assert _best_key_for_label("AMBITIOUS_RU500_sample_003", keys) == "ambitious_ru500"

    def test_no_match_returns_none(self):
        assert _best_key_for_label("unrelated", ["ambitious"]) is None


@pytest.mark.unit
class TestFrameHelpers:
    def test_extract_year_rows_accepts_dates_and_plain_years(self, two_scenario_config):
        years = [2025, 2026, 2027]
        df = build_report_frame(
            [("alpha_sample_001", "MetricA", "", [1.0, 2.0, 3.0])], years
        )
        df.iat[6, 0] = "01/01/2026 00.00"
        rows_idx, found_years = extract_year_rows(df.values)
        assert found_years == years
        assert rows_idx == [5, 6, 7]

    def test_metric_columns_by_header_and_scenario(self, two_scenario_config):
        df = build_report_frame(
            [
                ("alpha_sample_001", "MetricA", "", [1.0]),
                ("beta_sample_001", "MetricA", "", [2.0]),
                ("alpha_sample_001", "Other", "", [3.0]),
            ],
            [2025],
        )
        assert metric_columns(df, "MetricA") == [1, 2]
        assert metric_columns(df, "MetricA", scenario_key="beta") == [2]

    def test_metric_columns_cache_cleared_on_reconfigure(self, two_scenario_config, tmp_path):
        df = build_report_frame([("alpha_sample_001", "MetricA", "", [1.0])], [2025])
        assert metric_columns(df, "MetricA") == [1]

        # reconfigure renames the scenario; a stale cache would keep the old match
        toml = tmp_path / "other.toml"
        toml.write_text('[scenarios]\nnames = ["gamma"]\n')
        config.configure(toml)
        assert metric_columns(df, "MetricA", scenario_key="gamma") == []
