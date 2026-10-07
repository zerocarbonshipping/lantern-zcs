<!--
SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
SPDX-License-Identifier: CC-BY-4.0
-->

# Contributing to Lantern

Thank you for your interest in improving Lantern. In principle anything can
be contributed: bug fixes, features and documentation.
Contributions are made by forking the repository and opening a pull request
against the `dev` branch.

Lantern is a companion tool for
[Navigate](https://github.com/zerocarbonshipping/navigate-zcs). Changes to
the simulation model itself belong in the Navigate repository; Lantern only
covers the visualization and post-processing layer on top of its outputs.

## Getting started

1. Fork the repository and clone your fork.
2. Install it with the dev tools: `pip install -e ".[dev]"`.
3. Create a branch from `dev` for your change.
4. Verify your setup by running `make lint`.

## What to contribute

Any valuable contribution is welcome.

**Bug fixes** can be submitted directly as a pull request. Describe the bug
and how the fix addresses it. If you have found a bug but do not plan to fix
it yourself, please open an issue instead.

**Large features**, such as new plot kinds and major refactors, should start
as a feature request issue. This
lets us align on scope and design before you invest significant effort.
Smaller features can be submitted directly as a pull request.

## Pull request expectations

- Target the `dev` branch. Maintainers merge `dev` into `main` when a
  release is cut.
- Keep each pull request focused on a single change. Unrelated fixes and
  refactors belong in separate pull requests.
- Write a clear description: what the change does, why it is needed, and how
  it was verified.
- Follow [`CODESTYLE.md`](CODESTYLE.md) and match the file you are editing.
- Update documentation when behavior changes: the README and the header of
  `plots.toml` or `style.toml` for user-facing changes, docstrings for code.
- Add an entry to `CHANGELOG.md` for user-visible changes. See the
  [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

## Checking a change

Lantern has no test suite. Before a pull request, run `make lint`, then open
Navigate results files with `lantern PATH` and look at the plots the change
touches. Changes that alter rendered plots or
exported CSVs should explain the difference in the pull request description.

## Questions

Issues are the preferred way to ask. Whether you are unsure if a change needs
a feature request first, want to discuss a design, or have a question about
the tool, open an issue and we will get back to you.

### Note on AI Tools

The use of Generative AI and related tools is neither encouraged nor
discouraged. However, you are responsible for the quality of your own
contributions, and we kindly ask that you do not clutter the repository with
code or inputs you do not fully understand.
