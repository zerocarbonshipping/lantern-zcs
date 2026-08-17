"""Generate the synthetic report.csv bundled with this example.

The layout mirrors a combined Navigate report: row 0 holds sample labels,
row 2 metric headers, row 3 subcategory labels, and rows 5+ yearly data
with the year in the first column. Two scenarios ("ambitious" and
"conservative") with 20 samples each, over 2025-2050.

Run from the examples/ directory to regenerate report.csv:

    python make_report.py
"""

import csv

import numpy as np

YEARS = list(range(2025, 2051))
SCENARIOS = ["ambitious", "conservative"]
N_SAMPLES = 20
SUBCATS = ["FUEL_OIL", "METHANOL", "AMMONIA"]

rng = np.random.default_rng(seed=42)


def emissions_path(scenario):
    """Well-to-wake emissions: decline from ~100 to a scenario-dependent floor."""
    floor = 12.0 if scenario == "ambitious" else 45.0
    t = np.linspace(0.0, 1.0, len(YEARS))
    base = 100.0 * (1.0 - t) + floor * t
    noise = rng.normal(1.0, 0.08)
    wiggle = rng.normal(0.0, 1.5, len(YEARS)).cumsum() * 0.15
    return np.clip(base * noise + wiggle, 0.0, None)


def expenses_path(scenario):
    """Total expenses: rise from ~50, steeper for the ambitious scenario."""
    top = 105.0 if scenario == "ambitious" else 80.0
    t = np.linspace(0.0, 1.0, len(YEARS))
    base = 50.0 + (top - 50.0) * t ** 1.3
    noise = rng.normal(1.0, 0.06)
    wiggle = rng.normal(0.0, 1.0, len(YEARS)).cumsum() * 0.1
    return np.clip(base * noise + wiggle, 0.0, None)


def energy_paths(scenario):
    """Consumed energy per fuel: fuel oil phases out, methanol and ammonia grow."""
    speed = 1.0 if scenario == "ambitious" else 0.55
    t = np.linspace(0.0, 1.0, len(YEARS)) * speed
    total = 200.0 * (1.0 + 0.2 * np.linspace(0.0, 1.0, len(YEARS)))
    fuel_oil_share = np.clip(1.0 - 1.1 * t, 0.05, 1.0)
    methanol_share = np.clip(0.7 * t, 0.0, 0.6)
    ammonia_share = np.clip(1.0 - fuel_oil_share - methanol_share, 0.0, None)
    shares = [fuel_oil_share, methanol_share, ammonia_share]
    noise = rng.normal(1.0, 0.07)
    return [np.clip(total * s * noise, 0.0, None) for s in shares]


# each sample contributes 5 columns: 2 single metrics + 3 energy subcategories
label_row, header_row, subcat_row = [""], [""], [""]
columns = []
for scenario in SCENARIOS:
    for i in range(1, N_SAMPLES + 1):
        label = f"{scenario}_sample_{i:03d}"
        sample_cols = [emissions_path(scenario), expenses_path(scenario)]
        sample_cols += energy_paths(scenario)
        headers = ["TotalEquivalentWTW", "Expenses"] + ["ConsumedEnergy"] * len(SUBCATS)
        subcats = ["", ""] + SUBCATS
        for col, header, subcat in zip(sample_cols, headers, subcats):
            label_row.append(label)
            header_row.append(header)
            subcat_row.append(subcat)
            columns.append(col)

rows = [
    label_row,
    [""] * len(label_row),
    header_row,
    subcat_row,
    [""] * len(label_row),
]
for y_idx, year in enumerate(YEARS):
    rows.append([str(year)] + [f"{col[y_idx]:.4f}" for col in columns])

with open("report.csv", "w", newline="") as f:
    csv.writer(f).writerows(rows)

print(f"Wrote report.csv: {len(rows)} rows x {len(label_row)} columns")
