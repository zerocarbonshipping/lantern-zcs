# Contributing to Lantern

Thank you for your interest in improving Lantern. In principle anything can
be contributed: bug fixes, features, plots and documentation. Contributions
are made by forking the repository and opening a pull request against the
`dev` branch.

Lantern is a companion tool for
[Navigate](https://github.com/zerocarbonshipping/navigate-zcs). Changes to
the simulation model or to what its results files hold belong in the
Navigate repository; Lantern only covers plotting those files.

## Getting started

1. Fork the repository and clone your fork.
2. Install it with the dev tools into a Python 3.12+ environment, conda or
   venv: `pip install -e ".[dev]"`.
3. Create a branch from `dev` for your change.
4. Verify your setup by running `ruff check lantern`,
   `ruff format --check lantern` and `mypy`.

## What to contribute

Any valuable contribution is welcome.

**Bug fixes** can be submitted directly as a pull request. Describe the bug
and how the fix addresses it. If you have found a bug but do not plan to fix
it yourself, please open an issue instead.

**Large features**, such as new plot kinds, changes to the keys of
`plots.yaml`, `labels.yaml` or `theme.yaml`, and major refactors, should
start as an issue. This lets us align on scope and design before you invest
significant effort. Smaller features can be submitted directly as a pull
request.

## Pull request expectations

- Target the `dev` branch.
- Keep each pull request focused on a single change. Unrelated fixes and
  refactors belong in separate pull requests.
- Title the pull request with one imperative sentence stating the outcome:
  no prefix, no "(#N)", under about 65 characters. The squash merge makes it
  the commit subject and appends " (#N)". For a single-commit pull request
  GitHub proposes the commit subject instead, so make the two equal.
- Write a clear description: what the change does, why it is needed, and how
  it was checked.
- Follow the code style: `ruff` and `mypy`, configured in `pyproject.toml`,
  enforce the mechanical rules. No lint or type suppressions in code: no
  `noqa`, no `type: ignore`; fix the code, or change the rule for everyone in
  the configuration. Beyond that, match the file you are editing.
- Update documentation when behavior changes: the README, `PLOTS.md` and the
  headers of `plots.yaml`, `labels.yaml` and `theme.yaml` for user-facing
  changes, docstrings for code changes.

### Changelog

`CHANGELOG.md` records what a user of Lantern would notice: a command-line
argument added, renamed, removed or changed in meaning; a key of
`plots.yaml`, `labels.yaml` or `theme.yaml`, or what it does; the page; the
plots drawn and the HTML and CSV files written; the results files Lantern
reads; and the installation requirements. It also records bugs in any of
these, including errors in the documentation. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Nothing else gets an entry: no refactor, move, rename or removal inside
`lantern/` that leaves these alone, and no change to what Python code can
import. Typing, lint, CI and tooling changes get none either. A pull request
states its user-visible effect in its description.

An entry is one to three lines; related entries may share one bullet with a
sub-list, each item one to three lines. It states what the user sees and, for
a rename or removal, what to write instead, and it ends with the issue number
if there is one. How the change works belongs in the pull request, not the
changelog.

## Checking a change

Lantern has no test suite. Before a pull request, run the checks under
Getting started, then open Navigate results files with `lantern PATH` and
look at the plots the change touches. A pull request that changes rendered
plots or written HTML or CSV files explains the difference in its
description.

## Questions

Issues are the preferred way to ask. Whether you are unsure if a change needs
an issue first, want to discuss a design, or have a question about the tool,
open an issue and we will get back to you.

## AI tools

The use of generative AI and related tools is neither encouraged nor
discouraged. You are responsible for the quality of your own contributions,
and we kindly ask that you do not clutter the repository with code or inputs
you do not fully understand.
