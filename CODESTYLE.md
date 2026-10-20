<!--
SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
SPDX-License-Identifier: CC-BY-4.0
-->

# Code Style

`ruff check lantern` enforces formatting basics, imports and naming. Beyond that:

- **Keep it small.** No options, flags or features nobody uses yet. Lantern
  plots what `plots.yaml` declares and names and orders its series as
  `labels.yaml` says; keep that split: nothing about looks in `plots.yaml`.
  The colours a label names come from `theme.yaml` in the repository, which is
  not part of the package; nothing in the package depends on it.
- **Docstrings:** one line per module, public function and class, saying what
  it does and any non-obvious why. No parameter sections.
- **Type hints** on signatures only.
- **Guard clauses** over nested `if`/`else`; a blank line after a guard.
- **Names** say what a thing is (`run_name`, not `rn`); module-private names
  start with `_`.
- **Errors:** raise specific exceptions with the offending value in the
  message; no bare `except:`.
- **Comments** only for a non-obvious why, lowercase, plain ASCII.
