# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

"""End-to-end CLI tests against the bundled example data."""

import pandas as pd
import pytest

from lantern import cli
from tests.conftest import EXAMPLES_DIR

REPORT = EXAMPLES_DIR / "report.csv"
CONFIG = EXAMPLES_DIR / "lantern.toml"


def run_cli(monkeypatch, *argv):
    monkeypatch.setattr("sys.argv", ["lantern", *map(str, argv)])
    cli.main()


@pytest.mark.unit
class TestDiscoveryCommands:
    def test_list_scenarios(self, monkeypatch, capsys):
        run_cli(monkeypatch, REPORT, "--config", CONFIG, "--list-scenarios")
        out = capsys.readouterr().out
        assert "ambitious" in out
        assert "conservative" in out
        assert "2 unique scenario(s)" in out

    def test_validate_reports_no_issues(self, monkeypatch, capsys):
        run_cli(monkeypatch, REPORT, "--config", CONFIG, "--validate")
        out = capsys.readouterr().out
        assert "No issues found" in out

    def test_init_writes_starter_config(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        run_cli(monkeypatch, REPORT, "--init")
        generated = (tmp_path / "lantern.toml").read_text()
        assert "ambitious" in generated
        assert "conservative" in generated
        assert "[weights.single]" in generated
        # header detection must find the metric-header row (2), not the
        # sample-label row (0)
        assert "header_row = 2" in generated
        assert 'TotalEquivalentWTW = "totalequivalentwtw"' in generated
        assert 'header = "ConsumedEnergy"' in generated
        assert "ambitious_sample_001" not in generated


class TestFullRender:
    def test_quantiles_render_produces_plots_and_exports(self, monkeypatch, tmp_path):
        outdir = tmp_path / "out"
        run_cli(monkeypatch, REPORT, "--config", CONFIG, "--outdir", outdir)

        for name in ["emissions.html", "expenses.html", "consumed_energy_grid.html"]:
            assert (outdir / name).exists()
            for scenario in ["ambitious", "conservative"]:
                assert (outdir / scenario / name).exists()

        percentiles = pd.read_csv(outdir / "percentiles.csv")
        assert list(percentiles.columns) == [
            "Metric", "Scenario", "Subcategory", "Year", "p5", "p50", "p95",
        ]
        assert set(percentiles["Scenario"]) == {"ambitious", "conservative"}
        assert set(percentiles["Metric"]) == {
            "TotalEquivalentWTW", "Expenses", "ConsumedEnergy",
        }
        # bands must be ordered at every year
        assert (percentiles["p5"] <= percentiles["p50"]).all()
        assert (percentiles["p50"] <= percentiles["p95"]).all()

        # representatives export keeps the original layout: label row on top,
        # one chosen sample per scenario
        reps = pd.read_csv(outdir / "representatives.csv", header=None, low_memory=False)
        labels = set(str(v) for v in reps.iloc[0, 1:])
        assert len(labels) == 2
        assert any("ambitious" in lab for lab in labels)
        assert any("conservative" in lab for lab in labels)

    def test_traces_render(self, monkeypatch, tmp_path):
        outdir = tmp_path / "traces_out"
        run_cli(monkeypatch, REPORT, "--config", CONFIG, "--mode", "traces", "--outdir", outdir)
        assert (outdir / "emissions.html").exists()

    def test_missing_csv_is_reported_not_raised(self, monkeypatch, tmp_path, caplog):
        run_cli(monkeypatch, tmp_path / "missing.csv", "--config", CONFIG)
        assert any("not found" in r.message for r in caplog.records)
