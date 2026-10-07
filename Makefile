# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

# run in an environment with the dev extras: pip install -e ".[dev]"
lint:
	ruff check lantern
	reuse lint
