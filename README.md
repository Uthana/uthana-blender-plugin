# Uthana Blender plugin

<img height="48" alt="image" src="https://github.com/user-attachments/assets/cc4391c2-fa9c-4ad3-95d4-292b512d9007" /> <img width="48" height="48" alt="image" src="https://github.com/user-attachments/assets/5d0c7249-a40e-4c64-ad13-bf03edff7382" />
 <img height="48" alt="image" src="https://github.com/user-attachments/assets/27c0e600-242f-4220-98df-07a8e0e7f1ef" />

---

Use Uthana foundation models directly in Blender to generate, preview, and apply lifelike human motion without leaving your animation workflow.

Latest release: https://github.com/Uthana/uthana-blender-plugin/releases/latest (v1.0.0)

## Features

Use the built-in panel workflow in `View3D > Sidebar > Uthana` for easy access to all features:

- Text to motion: generate motion from a natural-language prompt
- Video to motion: extract motion from a video file
- Browse and preview your Uthana motions directly in Blender
- Download motions to your scene and apply them to your characters

## Compatibility

- Blender `4.0+`
- Uthana account and API key (get it from https://uthana.com/app/account)
- Requires an active internet connection while using the add-on

## Installation

### Option A: Install from GitHub Releases (recommended)

1. Download the latest add-on zip from this repository's Releases page.
2. In Blender, open `Edit > Preferences > Add-ons`.
3. Click `Install...` and select the downloaded zip.
4. Enable the add-on named `Uthana`.
5. Open the `Uthana` tab in the 3D View sidebar (`N` key).

### Option B: Build from source

```sh
git clone https://github.com/Uthana/uthana-blender-plugin.git
cd uthana-blender-plugin
poetry install --no-root
make build-zip
```

Then install `dist/uthana-<version>.zip` from Blender Preferences.

## Quick start

1. Open Blender and go to `View3D > Sidebar > Uthana`.

2. Expand `Config` and paste your API key (use the default domain `uthana.com`).
    <img width="473" height="270" alt="blender_configure" src="https://github.com/user-attachments/assets/c8150826-62bc-4cff-9673-7bfe5b3697fa" />

3. Click the connection/test action in the UI to verify your API key is valid.

4. (Optional) Upload a character mesh. Uthana will automatically rig and retarget your characters to every motion you generate.
    <img width="476" height="376" alt="blender_charUpload" src="https://github.com/user-attachments/assets/176aeb69-3734-4e3c-b8f8-be691d424dc4" />

5. Generate a motion:
    
    - **Text to motion** — write a prompt and generate a motion. For best results, describe a single motion, and begin your prompt with "A person..."
  
      <img width="521" height="372" alt="blender_t2m" src="https://github.com/user-attachments/assets/87925d25-3c79-4520-9ee4-c867489d2041" />

    - **Video to motion** — upload a video file of yourself or someone else performing a motion, then wait for processing (can take 60+ seconds).
  
      <img width="471" height="333" alt="blender_v2m" src="https://github.com/user-attachments/assets/ee2def88-e42b-4b66-b289-85fd522ffba5" />

6. Preview the motion in the viewer before downloading (you can also view all of your generated motions on <a href="https://uthana.com/app" target="_blank">uthana.com</a>). When you're ready to use a motion, click `Download and import` to add it to your scene.
    <img width="519" height="645" alt="blender_preview_and_download" src="https://github.com/user-attachments/assets/ffcec04c-80c2-45f0-a457-069bc734a3fe" />

## Contributing and development setup

This repository uses Poetry for dependency and tooling management. The virtual environment is configured at `.venv/`.

### Prerequisites

- Python `3.11` (recommended to use [pyenv](https://github.com/pyenv/pyenv) for version management)
- Poetry (https://python-poetry.org/docs/#installation)

### Contributing

1. Create a branch for your change (`git checkout -b feature/my-feature`).
2. When you have tested your changes, run `make format`, `make lint`, and `make typecheck`.
3. Run `make precommit` to run the pre-commit hooks.
4. Open a pull request with a clear description explaining the changes, and include any test notes.
5. If you are fixing a bug form an existing GitHub issue, reference the issue in the pull request description.

### Code of conduct

1. We expect all contributors to follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) code of conduct. Please be respectful and considerate of others when contributing to this project.
2. Use of AI tools is allowed, but please be transparent about your use of AI tools in your pull request, and ensure that you have reviewed and understood the code you are contributing.

## Development setup

### Setup

```sh
poetry install --no-root
```

`--no-root` is intentional because this project is a Blender add-on, not a published Python package.

### Common commands

```sh
make lint
make format
make typecheck
make precommit-install
make precommit
make build-zip
make release-prepare VERSION=1.2.3
```

Equivalent Poetry commands:

```sh
poetry run ruff check src scripts
poetry run ruff format src scripts
poetry run mypy src scripts
poetry run pre-commit run --all-files
poetry run python scripts/build_addon.py
poetry run python scripts/release.py prepare --version 1.2.3
```

### Pre-commit hooks

Install hooks once per clone:

```sh
make precommit-install
```

Hooks run Ruff linting/formatting and basic file hygiene checks.

### CI build and release policy

`dist/` artifacts are generated in CI and are not committed to the repository.

- Pull requests and pushes to `main` run the `Build uthana-blender-plugin` workflow, which executes `make build-zip` and uploads the built zip as a workflow artifact.
- Tags matching `v*` run the `Release uthana-blender-plugin` workflow, which validates SemVer and version sync, builds the zip, and publishes it to a GitHub Release.
- Enable branch protection on `main` and require the `Build uthana-blender-plugin` check before merging.

### Versioning and release tags

Releases follow SemVer with optional RC prereleases:

- Stable: `vMAJOR.MINOR.PATCH` (example: `v1.2.3`)
- Prerelease: `vMAJOR.MINOR.PATCH-rc.N` (example: `v1.2.3-rc.0`)

`src/__init__.py` (`bl_info["version"]`) and `pyproject.toml` store the base version only (`MAJOR.MINOR.PATCH`). The RC suffix lives in the Git tag.

Use this flow to create a release safely:

1. Ensure your worktree is clean and you are on the branch you want to release from.
2. Run:
   - Stable: `make release-prepare VERSION=1.2.3`
   - RC: `make release-prepare VERSION=1.2.3-rc.0`
3. Push commit and tag: `git push origin <branch> --follow-tags`

The helper script prevents tag reuse/clobber by checking existing local and remote tags before creating a new one.

### Format on save

If you are using VS Code or Cursor, the workspace settings in `.vscode/settings.json` automatically configure Ruff as the Python formatter and run lint fixes on save (including in Cursor/VS Code environments).

## Repository layout

- `src/`: Blender add-on source (registered as module `uthana` in release zips)
- `src/ui/`: panels, operators, modal operators, and UI properties
- `scripts/`: build and helper scripts
- `dist/`: generated release artifacts

## Troubleshooting

- **Add-on not visible in Blender**: ensure it is enabled in Preferences and restart Blender.
- **Auth/API failures**: verify API key and domain in the `Config` section.
- **Video or character uploads fail**: confirm network access and supported file extensions.
- **Type-check noise around `bpy`**: this repo uses `fake-bpy-module` for development typing support.

## Contributing

Contributions are welcome.

1. Create a branch for your change.
2. Run `make format`, `make lint`, and `make typecheck`.
3. Run `make precommit`.
4. Open a pull request with a clear description and test notes.

For bugs and feature requests, open a GitHub issue.

## Documentation and project support

- API docs: https://uthana.com/docs/api
- Issues: use this repository's GitHub issue tracker
- Support: join the Uthana Discord: https://discord.gg/PbMzMPSyTG or email support (at) uthana.com

## License

Licensed under the Apache License 2.0. See `LICENSE`.
