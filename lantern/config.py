# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

# config.py
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

logger = logging.getLogger(__name__)

# -----------------------------
# Public API (module attributes)
# -----------------------------
DATA_START_ROW: int
HEADER_ROW: int
SUBCAT_ROW: int

SCENARIOS: List[str]
COLOR_MAP: Dict[str, str]
SCENARIO_TITLES: Dict[str, str]
SCENARIO_GROUPS: Dict[str, List[str]]
_ALL_SUB_SCENARIOS: List[str]
_SUB_TO_MAIN: Dict[str, str]

SINGLE_METRICS: Dict[str, str]
MULTI_METRICS: List[Tuple[str, str, int]]
SKIP_SUB: Dict[str, Set[str]]

WEIGHTS_SINGLE: Dict[str, float]
WEIGHTS_MULTI: Dict[str, float]

QUANTILES_SHOW_MEDIAN: bool
QUANTILES_Q_LOW: float
QUANTILES_Q_HIGH: float
MANUAL_REPRESENTATIVES: Dict[str, str]
SHOW_REPRESENTATIVES: bool
REP_TARGETS: List["RepTarget"]

MIN_ROW_HEIGHT: int
FIXED_HEIGHT: int
MAX_TRACES_PER_SUBPLOT: int

OUTPUT_DIR: Path

PLOTS: "Plots"
PPT: "PptExport"

TRACES_LINE_WIDTH: float
TRACES_OPACITY: float
TRACES_COMPLETE_LEGEND: bool
TRACES_SCENARIO_LEGEND: bool
TRACES_PER_TRACE_DASHING: bool
TRACES_DASH_CYCLE: List[str]

# --------------------------------
# Internal config model & defaults
# --------------------------------


@dataclass
class CsvLayout:
    data_start_row: int = 5
    header_row: int = 2
    subcategory_row: int = 3


@dataclass
class Plots:
    min_row_height: int = 400
    fixed_height: int = 1200
    paper_bgcolor: str = "white"
    plot_bgcolor: str = "white"
    show_legend: bool = True
    legend_orientation: str = "h"
    legend_x: float = 1.0
    legend_y: float = 1.02
    legend_xanchor: str = "right"
    legend_yanchor: str = "bottom"
    margin_top: int = 60
    margin_right: int = 40
    margin_bottom: int = 40
    margin_left: int = 40
    y_rangemode: str = "tozero"
    traces_tickformat: str = "%Y"
    quarterly_tickformat: str = "Q%q %Y"


@dataclass
class Performance:
    max_traces_per_subplot: int = 200


@dataclass
class TracesStyle:
    line_width: float = 1.0   # default thickness for traces mode
    opacity: float = 0.25     # default opacity for traces mode
    complete_legend: bool = False        # show every trace in legend
    scenario_legend: bool = True         # show one legend entry per scenario
    per_trace_dashing: bool = False      # cycle dash styles per trace
    dash_cycle: List[str] = field(default_factory=lambda: [
        "solid", "dash", "dot", "longdash", "dashdot", "longdashdot"
    ])


@dataclass
class Output:
    dir: str = "2_output"


@dataclass
class Metrics:
    # row-2 header -> short key
    single: Dict[str, str] = field(default_factory=lambda: {
        "TotalEquivalentWTW": "emissions",
        "Expenses": "expenses",
        "IntensityTotalEquivalentWTW": "intensity",
    })
    # list of {header, key, grid_cols}
    multi: List[Dict[str, Any]] = field(default_factory=lambda: [
        {"header": "ConsumedEnergy", "key": "consumed_energy", "grid_cols": 3},
        {"header": "InstalledPower", "key": "installed_power", "grid_cols": 2},
        {"header": "FuelTypeEnergy", "key": "fuel_type_energy", "grid_cols": 3},
    ])
    # {key -> [subcats to skip]}
    skip_sub: Dict[str, List[str]] = field(default_factory=lambda: {
        "installed_power": ["DIESEL", "HYDROGEN"],
        "fuel_type_energy": ["HYDROGEN"],
    })


@dataclass
class Scenarios:
    names: List[str] = field(default_factory=lambda: ["ambitious", "pledged", "confirmed", "removed"])
    colors: Dict[str, str] = field(default_factory=lambda: {
        "ambitious": "#6ABF8B",
        "pledged":   "#4DA6CE",
        "confirmed": "#D49B2C",
        "removed":   "#DA6C60",
    })
    titles: Dict[str, str] = field(default_factory=dict)
    groups: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class Weights:
    # keys must match the *short keys* from Metrics.single / Metrics.multi
    single: Dict[str, float] = field(default_factory=lambda: {
        "emissions": 0.4,
        "expenses":  0.1,
        "intensity": 0.0,
    })
    multi: Dict[str, float] = field(default_factory=lambda: {
        "consumed_energy":  0.0,
        "installed_power":  0.3,
        "fuel_type_energy": 0.2,
    })


@dataclass
class Quantiles:
    # If true, draw the p50 (median) line in quantiles mode.
    # Default is False per request (hide median by default).
    show_median: bool = False
    median_line_width: float = 3.0
    median_dash: Optional[str] = None
    band_alpha: float = 0.18
    q_low: float = 5.0
    q_high: float = 95.0


@dataclass
class RepTarget:
    percentile: float = 50.0
    label: str = "representative"
    dash: Optional[str] = None
    line_width: float = 2.5
    show: bool = True


@dataclass
class Representatives:
    # Map scenario -> pattern used to pick the representative sample label
    # (case-insensitive substring match against the label row).
    manual: Dict[str, str] = field(default_factory=dict)
    show: bool = True
    line_width: float = 2.5
    dash: Optional[str] = None
    darken_factor: float = 0.75
    targets: List["RepTarget"] = field(default_factory=lambda: [RepTarget()])


@dataclass
class PptExport:
    enabled: bool = False
    width_px: int = 1300
    height_px: int = 731
    scale: float = 2.0
    transparent: bool = False

    # Plotly's default font stack; set font_family in lantern.toml to use a
    # locally installed brand font instead.
    font_family: str = "Open Sans, verdana, arial, sans-serif"
    base_font_size: int = 14

    title_show: bool = True
    title_size: int = 16
    title_prefix: str = ""
    title_suffix: str = ""

    legend_show: bool = True
    legend_orientation: str = "h"
    legend_x: float = 1.0
    legend_y: float = 1.02
    legend_xanchor: str = "right"
    legend_yanchor: str = "bottom"

    margin_top: int = 10
    margin_right: int = 20
    margin_bottom: int = 40
    margin_left: int = 60

    axis_linewidth: float = 0.5

    x_show_line: bool = True
    x_show_ticks: bool = False
    x_show_ticklabels: bool = True
    x_show_grid: bool = False
    x_tick_angle: int = 0
    x_title_show: bool = True
    x_title_text: str = "Year"
    x_title_size: int = 14

    y_show_line: bool = True
    y_show_ticks: bool = False
    y_show_ticklabels: bool = False
    y_show_grid: bool = False
    y_title_show: bool = True
    y_title_size: int = 14

    median_line_width: float = 3.0
    representative_width: float = 2.0
    representative_dash: str = "dash"
    band_alpha: float = 0.18

    ppt_subdir: str = "ppt"
    filename_suffix: str = "_ppt"


@dataclass
class RootConfig:
    csv_layout: CsvLayout = field(default_factory=CsvLayout)
    scenarios: Scenarios = field(default_factory=Scenarios)
    metrics: Metrics = field(default_factory=Metrics)
    plots: Plots = field(default_factory=Plots)
    performance: Performance = field(default_factory=Performance)
    traces: TracesStyle = field(default_factory=TracesStyle)
    output: Output = field(default_factory=Output)
    quantiles: Quantiles = field(default_factory=Quantiles)
    representatives: Representatives = field(default_factory=Representatives)
    weights: Weights = field(default_factory=Weights)
    ppt: PptExport = field(default_factory=PptExport)

# ----------------
# Loader + binder
# ----------------


def _read_toml(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge *override* into *base* (mutates *base*)."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _apply_mode_overrides(raw: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """
    If *raw* contains a ``[mode.<mode>.*]`` block, deep-merge those
    overrides into the top-level sections, then drop the ``mode`` key
    so downstream code never sees it.
    """
    import copy
    result = copy.deepcopy(raw)
    mode_block = result.pop("mode", None)
    if not mode_block or not isinstance(mode_block, dict):
        return result
    overrides = mode_block.get(mode)
    if not overrides or not isinstance(overrides, dict):
        return result
    _deep_merge(result, overrides)
    return result


def _as_list(obj) -> List[Any]:
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    return [obj]


def _merge_into_defaults(raw: Dict[str, Any]) -> RootConfig:
    cfg = RootConfig()
    # csv_layout
    cl = raw.get("csv_layout", {})
    cfg.csv_layout.data_start_row = int(cl.get("data_start_row", cfg.csv_layout.data_start_row))
    cfg.csv_layout.header_row = int(cl.get("header_row", cfg.csv_layout.header_row))
    cfg.csv_layout.subcategory_row = int(cl.get("subcategory_row", cfg.csv_layout.subcategory_row))

    # traces
    tr = raw.get("traces", {})
    try:
        cfg.traces.line_width = float(tr.get("line_width", cfg.traces.line_width))
    except Exception:
        pass
    try:
        cfg.traces.opacity = float(tr.get("opacity", cfg.traces.opacity))
    except Exception:
        pass
    try:
        cfg.traces.complete_legend = bool(tr.get("complete_legend", cfg.traces.complete_legend))
    except Exception:
        pass
    try:
        cfg.traces.scenario_legend = bool(tr.get("scenario_legend", cfg.traces.scenario_legend))
    except Exception:
        pass
    try:
        cfg.traces.per_trace_dashing = bool(tr.get("per_trace_dashing", cfg.traces.per_trace_dashing))
    except Exception:
        pass
    if "dash_cycle" in tr:
        vals = tr.get("dash_cycle", [])
        if isinstance(vals, list):
            cfg.traces.dash_cycle = [str(x) for x in vals]

    # scenarios
    sc = raw.get("scenarios", {})
    # Groups take precedence over names
    if "groups" in sc:
        cfg.scenarios.groups = {
            str(k).lower(): [str(s).lower() for s in v]
            for k, v in sc["groups"].items()
        }
        # Derive scenario names from group keys
        cfg.scenarios.names = list(cfg.scenarios.groups.keys())
    elif "names" in sc:
        cfg.scenarios.names = [str(x) for x in sc["names"]]
    # Colors (keyed by main scenario names)
    if "colors" in sc:
        cfg.scenarios.colors = {str(k).lower(): str(v) for k, v in sc["colors"].items()}
    if "titles" in sc:
        cfg.scenarios.titles = {str(k).lower(): str(v) for k, v in sc["titles"].items()}

    # metrics.single
    mt = raw.get("metrics", {})
    if "single" in mt:
        cfg.metrics.single = {str(k): str(v) for k, v in mt["single"].items()}
    else:
        cfg.metrics.single = cfg.metrics.single  # keep defaults

    # metrics.multi (list of tables with header/key/grid_cols)
    if "multi" in mt:
        multi_list: List[Dict[str, Any]] = []
        for item in mt["multi"]:
            missing = [k for k in ("header", "key") if k not in item]
            if missing:
                raise ValueError(
                    f"[[metrics.multi]] entry is missing required key(s) "
                    f"{missing}: {item!r}")

            multi_list.append({
                "header": str(item["header"]),
                "key": str(item["key"]),
                "grid_cols": int(item.get("grid_cols", 3)),
            })
        cfg.metrics.multi = multi_list
    else:
        cfg.metrics.multi = cfg.metrics.multi  # keep defaults

    # metrics.skip_sub (lists -> sets later)
    if "skip_sub" in mt:
        cfg.metrics.skip_sub = {
            str(k): [str(x) for x in _as_list(v)]
            for k, v in mt["skip_sub"].items()
        }
    else:
        cfg.metrics.skip_sub = cfg.metrics.skip_sub  # keep defaults

    # plots
    pl = raw.get("plots", {})
    cfg.plots.min_row_height = int(pl.get("min_row_height", cfg.plots.min_row_height))
    cfg.plots.fixed_height = int(pl.get("fixed_height", cfg.plots.fixed_height))
    cfg.plots.paper_bgcolor = str(pl.get("paper_bgcolor", cfg.plots.paper_bgcolor))
    cfg.plots.plot_bgcolor = str(pl.get("plot_bgcolor", cfg.plots.plot_bgcolor))
    cfg.plots.show_legend = bool(pl.get("show_legend", cfg.plots.show_legend))
    cfg.plots.legend_orientation = str(pl.get("legend_orientation", cfg.plots.legend_orientation))
    cfg.plots.legend_x = float(pl.get("legend_x", cfg.plots.legend_x))
    cfg.plots.legend_y = float(pl.get("legend_y", cfg.plots.legend_y))
    cfg.plots.legend_xanchor = str(pl.get("legend_xanchor", cfg.plots.legend_xanchor))
    cfg.plots.legend_yanchor = str(pl.get("legend_yanchor", cfg.plots.legend_yanchor))
    cfg.plots.margin_top = int(pl.get("margin_top", cfg.plots.margin_top))
    cfg.plots.margin_right = int(pl.get("margin_right", cfg.plots.margin_right))
    cfg.plots.margin_bottom = int(pl.get("margin_bottom", cfg.plots.margin_bottom))
    cfg.plots.margin_left = int(pl.get("margin_left", cfg.plots.margin_left))
    cfg.plots.y_rangemode = str(pl.get("y_rangemode", cfg.plots.y_rangemode))
    cfg.plots.traces_tickformat = str(pl.get("traces_tickformat", cfg.plots.traces_tickformat))
    cfg.plots.quarterly_tickformat = str(pl.get("quarterly_tickformat", cfg.plots.quarterly_tickformat))

    # performance
    pf = raw.get("performance", {})
    cfg.performance.max_traces_per_subplot = int(
        pf.get("max_traces_per_subplot", cfg.performance.max_traces_per_subplot)
    )

    wt = raw.get("weights", {})
    if "single" in wt:
        cfg.weights.single = {str(k): float(v) for k, v in wt["single"].items()}
    else:
        cfg.weights.single = cfg.weights.single  # keep defaults
    if "multi" in wt:
        cfg.weights.multi = {str(k): float(v) for k, v in wt["multi"].items()}
    else:
        cfg.weights.multi = cfg.weights.multi  # keep defaults

    # quantiles
    qt = raw.get("quantiles", {})
    cfg.quantiles.show_median = bool(qt.get("show_median", cfg.quantiles.show_median))
    cfg.quantiles.median_line_width = float(qt.get("median_line_width", cfg.quantiles.median_line_width))
    cfg.quantiles.median_dash = None if "median_dash" not in qt or qt.get("median_dash") is None else str(qt.get("median_dash"))
    cfg.quantiles.band_alpha = float(qt.get("band_alpha", cfg.quantiles.band_alpha))
    if "q_low" in qt:
        cfg.quantiles.q_low = float(qt["q_low"])
    if "q_high" in qt:
        cfg.quantiles.q_high = float(qt["q_high"])

    # representatives (manual overrides)
    rep = raw.get("representatives", {})
    if isinstance(rep, dict):
        _rep_reserved = {"show", "line_width", "dash", "darken_factor", "targets"}
        cfg.representatives.manual = {
            str(k).lower(): str(v)
            for k, v in rep.items()
            if k not in _rep_reserved
        }
        if "show" in rep:
            cfg.representatives.show = bool(rep["show"])
        if "line_width" in rep:
            cfg.representatives.line_width = float(rep["line_width"])
        cfg.representatives.dash = None if "dash" not in rep or rep.get("dash") is None else str(rep.get("dash"))
        if "darken_factor" in rep:
            cfg.representatives.darken_factor = float(rep["darken_factor"])
        if "targets" in rep and isinstance(rep["targets"], list):
            targets = []
            for t in rep["targets"]:
                if not isinstance(t, dict):
                    continue
                rt = RepTarget()
                if "percentile" in t:
                    rt.percentile = float(t["percentile"])
                if "label" in t:
                    rt.label = str(t["label"])
                if "dash" in t:
                    rt.dash = None if t["dash"] is None else str(t["dash"])
                if "line_width" in t:
                    rt.line_width = float(t["line_width"])
                if "show" in t:
                    rt.show = bool(t["show"])
                targets.append(rt)
            if targets:
                cfg.representatives.targets = targets

    # output
    out = raw.get("output", {})
    cfg.output.dir = str(out.get("dir", cfg.output.dir))

    # ppt export
    ppt = raw.get("ppt", {})
    for k, v in ppt.items():
        if hasattr(cfg.ppt, k):
            # basic type coercion
            current = getattr(cfg.ppt, k)
            if isinstance(current, bool):
                setattr(cfg.ppt, k, bool(v))
            elif isinstance(current, int):
                setattr(cfg.ppt, k, int(v))
            elif isinstance(current, float):
                setattr(cfg.ppt, k, float(v))
            else:
                setattr(cfg.ppt, k, str(v))
    return cfg


def _bind_globals(cfg: RootConfig) -> None:
    # Export module-level names expected by the rest of the codebase
    global DATA_START_ROW, HEADER_ROW, SUBCAT_ROW
    global SCENARIOS, COLOR_MAP, SCENARIO_TITLES, SCENARIO_GROUPS, _ALL_SUB_SCENARIOS, _SUB_TO_MAIN
    global SINGLE_METRICS, MULTI_METRICS, SKIP_SUB
    global MIN_ROW_HEIGHT, FIXED_HEIGHT, MAX_TRACES_PER_SUBPLOT
    global OUTPUT_DIR, SHOW_REPRESENTATIVES
    global QUANTILES_SHOW_MEDIAN, QUANTILES_Q_LOW, QUANTILES_Q_HIGH, MANUAL_REPRESENTATIVES, REP_TARGETS
    global WEIGHTS_SINGLE, WEIGHTS_MULTI
    global PLOTS, PPT, TRACES_LINE_WIDTH, TRACES_OPACITY, TRACES_COMPLETE_LEGEND
    global TRACES_SCENARIO_LEGEND, TRACES_PER_TRACE_DASHING, TRACES_DASH_CYCLE

    DATA_START_ROW = cfg.csv_layout.data_start_row
    HEADER_ROW = cfg.csv_layout.header_row
    SUBCAT_ROW = cfg.csv_layout.subcategory_row

    SCENARIOS = list(cfg.scenarios.names)
    COLOR_MAP = dict(cfg.scenarios.colors)
    SCENARIO_TITLES = dict(cfg.scenarios.titles)

    # Build grouping infrastructure
    if cfg.scenarios.groups:
        SCENARIO_GROUPS = dict(cfg.scenarios.groups)
    else:
        # Identity mapping: each scenario is its own group
        SCENARIO_GROUPS = {s: [s] for s in SCENARIOS}

    _ALL_SUB_SCENARIOS = []
    _SUB_TO_MAIN = {}
    seen_subs: Dict[str, str] = {}
    for main, subs in SCENARIO_GROUPS.items():
        for sub in subs:
            sub_l = sub.lower()
            if sub_l in seen_subs:
                logger.warning(
                    f"Sub-scenario '{sub_l}' in multiple groups: "
                    f"'{seen_subs[sub_l]}' and '{main}'"
                )
            seen_subs[sub_l] = main
            _ALL_SUB_SCENARIOS.append(sub_l)
            _SUB_TO_MAIN[sub_l] = main.lower()

    # Warn if main scenarios lack colors
    for main in SCENARIOS:
        if main not in COLOR_MAP:
            logger.warning(f"No color defined for scenario '{main}'")

    SINGLE_METRICS = dict(cfg.metrics.single)
    # Convert list of dicts -> list of tuples (header, short_key, grid_cols)
    MULTI_METRICS = [(m["header"], m["key"], m["grid_cols"]) for m in cfg.metrics.multi]
    # Convert lists -> sets
    SKIP_SUB = {k: set(v) for k, v in cfg.metrics.skip_sub.items()}

    MIN_ROW_HEIGHT = cfg.plots.min_row_height
    FIXED_HEIGHT = cfg.plots.fixed_height

    MAX_TRACES_PER_SUBPLOT = cfg.performance.max_traces_per_subplot

    OUTPUT_DIR = Path(cfg.output.dir)
    PLOTS = cfg.plots

    WEIGHTS_SINGLE = dict(cfg.weights.single)
    WEIGHTS_MULTI = dict(cfg.weights.multi)

    QUANTILES_SHOW_MEDIAN = bool(cfg.quantiles.show_median)
    QUANTILES_Q_LOW = float(cfg.quantiles.q_low)
    QUANTILES_Q_HIGH = float(cfg.quantiles.q_high)
    MANUAL_REPRESENTATIVES = dict(cfg.representatives.manual)
    SHOW_REPRESENTATIVES = bool(cfg.representatives.show)
    REP_TARGETS = list(cfg.representatives.targets)

    PPT = cfg.ppt

    TRACES_LINE_WIDTH = float(cfg.traces.line_width)
    TRACES_OPACITY = float(cfg.traces.opacity)
    TRACES_COMPLETE_LEGEND = bool(cfg.traces.complete_legend)
    TRACES_SCENARIO_LEGEND = bool(cfg.traces.scenario_legend)
    TRACES_PER_TRACE_DASHING = bool(cfg.traces.per_trace_dashing)
    TRACES_DASH_CYCLE = list(cfg.traces.dash_cycle)


# Keep last loaded config instance for introspection if needed
_LAST_CONFIG: Optional[RootConfig] = None


def _load_raw_default() -> Dict[str, Any]:
    """Return the raw TOML dict using the default search order (before merge)."""
    env = os.getenv("LANTERN_CONFIG")
    if env:
        p = Path(env)
        if p.exists():
            logger.debug(f"Loading config from LANTERN_CONFIG={p}")
            return _read_toml(p)
    local = Path("lantern.toml")
    if local.exists():
        logger.debug(f"Loading config from {local}")
        return _read_toml(local)
    logger.debug("No TOML config found — using built-in defaults.")
    return {}


def load_default_config() -> RootConfig:
    """
    Search order:
      1. Env var LANTERN_CONFIG pointing to a .toml file
      2. ./lantern.toml in current directory
      3. package defaults (no file)
    """
    return _merge_into_defaults(_load_raw_default())


def configure(path: Optional[str | Path], mode: Optional[str] = None) -> None:
    """
    Load a specific TOML and bind module-level constants.
    If *path* is None, uses the default search order.
    If *mode* is given (e.g. ``"traces"`` or ``"quantiles"``), any
    ``[mode.<mode>.*]`` overrides in the TOML are applied on top of
    the shared settings before merging into defaults.
    Call this from CLI as soon as arguments are parsed.
    """
    global _LAST_CONFIG
    # Clear metric_columns cache on config reload
    from .percentiles import clear_metric_columns_cache
    clear_metric_columns_cache()
    if path:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        raw = _read_toml(path)
        logger.debug(f"Loaded config from {path}")
    else:
        raw = _load_raw_default()

    if mode:
        raw = _apply_mode_overrides(raw, mode)

    cfg = _merge_into_defaults(raw)
    _bind_globals(cfg)
    _LAST_CONFIG = cfg


# Load once at import so the rest of the code has values.
# CLI can call configure() again with a specific file to override.
try:
    configure(None)
except Exception as e:  # pragma: no cover
    logger.exception(f"Failed to initialize configuration: {e}")
    # fall back to defaults if something goes wrong
    _bind_globals(RootConfig())
