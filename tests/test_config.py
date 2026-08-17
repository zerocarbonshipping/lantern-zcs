# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for TOML loading and module-global binding in config.py."""

import pytest

from lantern import config


@pytest.mark.unit
class TestDefaults:
    def test_builtin_defaults_bind_without_a_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config.configure(None)
        assert config.DATA_START_ROW == 5
        assert config.HEADER_ROW == 2
        assert config.SCENARIOS == ["ambitious", "pledged", "confirmed", "removed"]
        assert config.QUANTILES_Q_LOW == 5.0
        assert config.QUANTILES_Q_HIGH == 95.0

    def test_missing_explicit_config_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            config.configure(tmp_path / "nope.toml")


@pytest.mark.unit
class TestTomlBinding:
    def test_toml_values_override_defaults(self, tmp_path):
        toml = tmp_path / "lantern.toml"
        toml.write_text(
            "\n".join(
                [
                    "[csv_layout]",
                    "data_start_row = 7",
                    "[scenarios]",
                    'names = ["x", "y"]',
                    "[scenarios.colors]",
                    'x = "#111111"',
                    "[quantiles]",
                    "q_low = 10.0",
                    "q_high = 90.0",
                    "[output]",
                    'dir = "custom_out"',
                ]
            )
        )
        config.configure(toml)
        assert config.DATA_START_ROW == 7
        assert config.SCENARIOS == ["x", "y"]
        assert config.COLOR_MAP["x"] == "#111111"
        assert config.QUANTILES_Q_LOW == 10.0
        assert str(config.OUTPUT_DIR) == "custom_out"

    def test_scenario_groups_map_sub_to_main(self, tmp_path):
        toml = tmp_path / "lantern.toml"
        toml.write_text(
            "\n".join(
                [
                    "[scenarios.groups]",
                    'main_a = ["sub_1", "sub_2"]',
                    'main_b = ["sub_3"]',
                ]
            )
        )
        config.configure(toml)
        assert config._SUB_TO_MAIN["sub_1"] == "main_a"
        assert config._SUB_TO_MAIN["sub_3"] == "main_b"
        assert set(config._ALL_SUB_SCENARIOS) >= {"sub_1", "sub_2", "sub_3"}

    def test_env_var_config_is_used(self, tmp_path, monkeypatch):
        toml = tmp_path / "env_config.toml"
        toml.write_text('[output]\ndir = "from_env"\n')
        monkeypatch.setenv("LANTERN_CONFIG", str(toml))
        monkeypatch.chdir(tmp_path)
        config.configure(None)
        assert str(config.OUTPUT_DIR) == "from_env"


@pytest.mark.unit
class TestModeOverrides:
    def test_mode_section_applies_only_for_that_mode(self, tmp_path):
        toml = tmp_path / "lantern.toml"
        toml.write_text(
            "\n".join(
                [
                    "[output]",
                    'dir = "base_out"',
                    "[mode.traces.output]",
                    'dir = "traces_out"',
                ]
            )
        )
        config.configure(toml, mode="traces")
        assert str(config.OUTPUT_DIR) == "traces_out"

        config.configure(toml, mode="quantiles")
        assert str(config.OUTPUT_DIR) == "base_out"
