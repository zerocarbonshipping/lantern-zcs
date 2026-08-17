# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for representative-pathway selection in selection.py."""

import numpy as np
import pytest

from lantern import config
from lantern.selection import choose_representatives, mse_to_target_in_percentiles
from tests.conftest import build_report_frame

YEARS = [2025, 2026, 2027]


def _three_sample_frame(scenario):
    """Three samples where sample_002 sits exactly at the median every year."""
    return [
        (f"{scenario}_sample_001", "MetricA", "", [10.0, 11.0, 12.0]),
        (f"{scenario}_sample_002", "MetricA", "", [20.0, 21.0, 22.0]),
        (f"{scenario}_sample_003", "MetricA", "", [30.0, 31.0, 32.0]),
    ]


@pytest.mark.unit
class TestMseToTarget:
    def test_median_column_has_zero_mse(self, two_scenario_config):
        df = build_report_frame(_three_sample_frame("alpha"), YEARS)
        labels, mse = mse_to_target_in_percentiles(df, [5, 6, 7], [1, 2, 3], target_percentile=50.0)
        assert labels[1] == "alpha_sample_002"
        assert mse[1] == 0.0
        assert mse[0] > 0.0 and mse[2] > 0.0

    def test_extreme_target_prefers_extreme_column(self, two_scenario_config):
        df = build_report_frame(_three_sample_frame("alpha"), YEARS)
        _, mse = mse_to_target_in_percentiles(df, [5, 6, 7], [1, 2, 3], target_percentile=95.0)
        assert np.argmin(mse) == 2

    def test_empty_columns_return_empty(self, two_scenario_config):
        df = build_report_frame(_three_sample_frame("alpha"), YEARS)
        labels, mse = mse_to_target_in_percentiles(df, [5, 6, 7], [])
        assert labels == [] and mse.size == 0


@pytest.mark.unit
class TestChooseRepresentatives:
    def test_picks_median_sample_per_scenario(self, two_scenario_config):
        columns = _three_sample_frame("alpha") + _three_sample_frame("beta")
        df = build_report_frame(columns, YEARS)
        reps = choose_representatives(df, df.values, {"a": 1.0}, {})
        assert reps["alpha"][50.0]["sample_label"] == "alpha_sample_002"
        assert reps["beta"][50.0]["sample_label"] == "beta_sample_002"
        assert reps["alpha"][50.0]["weighted_score"] == 0.0

    def test_multiple_targets(self, two_scenario_config):
        df = build_report_frame(_three_sample_frame("alpha"), YEARS)
        reps = choose_representatives(df, df.values, {"a": 1.0}, {}, targets=[5.0, 50.0, 95.0])
        assert reps["alpha"][5.0]["sample_label"] == "alpha_sample_001"
        assert reps["alpha"][50.0]["sample_label"] == "alpha_sample_002"
        assert reps["alpha"][95.0]["sample_label"] == "alpha_sample_003"

    def test_zero_weights_select_nothing(self, two_scenario_config):
        df = build_report_frame(_three_sample_frame("alpha"), YEARS)
        reps = choose_representatives(df, df.values, {"a": 0.0}, {})
        assert reps == {}

    def test_manual_override_wins_at_p50(self, two_scenario_config, tmp_path):
        toml = tmp_path / "manual.toml"
        toml.write_text(
            "\n".join(
                [
                    "[scenarios]",
                    'names = ["alpha"]',
                    "[metrics.single]",
                    'MetricA = "a"',
                    "[weights.single]",
                    "a = 1.0",
                    # manual patterns are plain keys under [representatives]
                    "[representatives]",
                    'alpha = "sample_003"',
                ]
            )
        )
        config.configure(toml)
        df = build_report_frame(_three_sample_frame("alpha"), YEARS)
        reps = choose_representatives(df, df.values, {"a": 1.0}, {})
        assert reps["alpha"][50.0]["sample_label"] == "alpha_sample_003"

    def test_manual_override_falls_back_when_pattern_misses(self, two_scenario_config, tmp_path):
        toml = tmp_path / "manual.toml"
        toml.write_text(
            "\n".join(
                [
                    "[scenarios]",
                    'names = ["alpha"]',
                    "[metrics.single]",
                    'MetricA = "a"',
                    "[weights.single]",
                    "a = 1.0",
                    "[representatives]",
                    'alpha = "no_such_sample"',
                ]
            )
        )
        config.configure(toml)
        df = build_report_frame(_three_sample_frame("alpha"), YEARS)
        reps = choose_representatives(df, df.values, {"a": 1.0}, {})
        assert reps["alpha"][50.0]["sample_label"] == "alpha_sample_002"
