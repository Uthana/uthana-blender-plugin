# uthana-blender-plugin

Use Uthana foundation models from within Blender. Generate and refine lifelike human motion without leaving your animation workflow.

## Development setup

This repository uses Poetry for dependency and tooling management. The virtual environment is configured to live in the project at `.venv/`.

### Prerequisites

- Python 3.11
- Poetry

### Install

```sh
poetry install --no-root
```

`--no-root` is intentional because this repository is a Blender add-on project, not a published Python package.

## Daily commands

You can run tools directly with Poetry or use `make` shortcuts.

```sh
make lint
make format
make typecheck
make precommit-install
make precommit
```

Equivalent Poetry commands:

```sh
poetry run ruff check src scripts
poetry run ruff format src scripts
poetry run mypy src scripts
poetry run pre-commit run --all-files
```

Recurring helper scripts:

```sh
./scripts/run_precommit.sh
./scripts/build_release_zip.sh
```

## Format on save

Workspace settings in `.vscode/settings.json` configure Ruff as the Python formatter and run lint fixes on save. This applies when using VS Code-compatible editors (including Cursor).

## Pre-commit

Install hooks once per clone:

```sh
make precommit-install
```

Hooks run Ruff linting/formatting plus basic file hygiene checks.

## Building a Blender add-on zip

Use the build script to create a distributable zip:

```sh
make build-zip
```

This script:

- copies `src/` into a staged add-on module directory
- vendors runtime dependencies (for example `requests`) into the bundle
- writes `dist/uthana-<version>.zip` based on `bl_info["version"]`

Install that zip in Blender via Preferences -> Add-ons -> Install.

## Packaging guidance

For this repository, a Blender add-on zip is the primary release artifact. A PyPI package is not required unless you later decide to distribute shared SDK code separately from the add-on.
