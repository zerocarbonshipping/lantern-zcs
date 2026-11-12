"""
Fixtures: a Navigate results file of one run, a compiled file made from it, and the repository's plots.yaml.

fixtures/attribute_coverage.parquet is the results file of Navigate's attribute_coverage deck, which touches every
attribute of the model, so every plot of plots.yaml has data in it. The weekly navigate workflow makes it again from
Navigate's dev branch, in the navigate-zcs repository:

    navigate tests/end_to_end/simulations/attribute_coverage/attribute_coverage.nav -d assumptions --output-dir DIR
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from lantern import config

if TYPE_CHECKING:
    from collections.abc import Iterator

ROOT = Path(__file__).parent.parent
SINGLE = Path(__file__).parent / "fixtures" / "attribute_coverage.parquet"
SCALES = {"a": 1.0, "b": 2.0, "a_median": 1.0, "a_p05": 0.8, "a_p95": 1.2}
SUMMARIES = {"a": {"median": "a_median", "low": "a_p05", "high": "a_p95"}}


@pytest.fixture(scope="session", autouse=True)
def plots_yaml(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Read the repository's plots.yaml, from a copy, never one in the working or home folder."""
    path = tmp_path_factory.mktemp("config") / "plots.yaml"
    shutil.copy(ROOT / "configs" / "plots.yaml", path)

    # PLOTS_FILES is fixed when lantern.config is imported, so changing folder alone would not do
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(config, "PLOTS_FILES", (path,))
        yield path


@pytest.fixture(autouse=True)
def working_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run each test in a folder of its own, where --plot and --data write."""
    monkeypatch.chdir(tmp_path)

    return tmp_path


@pytest.fixture(scope="session")
def single() -> Path:
    """Return the results file of one run."""
    return SINGLE


@pytest.fixture(scope="session")
def compiled(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Write a compiled file, study.parquet, of the runs a and b, and a's summary over its samples, as Horizon does."""
    # Polars only after lantern, which sets the threads Polars takes before Polars reads the setting on import
    import polars as pl

    meta = json.loads(pl.read_parquet_metadata(SINGLE)["navigate"])
    rows = pl.read_parquet(SINGLE)
    runs = [
        rows.select(pl.lit(run).alias("run"), pl.exclude("value"), pl.col("value") * scale) for run, scale in SCALES.items()
    ]
    path = tmp_path_factory.mktemp("compiled") / "study.parquet"
    pl.concat(runs).write_parquet(path, metadata={"navigate": json.dumps(meta | {"summaries": SUMMARIES})})

    return path
