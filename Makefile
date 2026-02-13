.PHONY: install lint format typecheck precommit-install precommit build-zip release-prepare

install:
	poetry install --no-root

lint:
	poetry run ruff check src scripts

format:
	poetry run ruff format src scripts

typecheck:
	poetry run mypy src scripts

precommit-install:
	poetry run pre-commit install

precommit:
	poetry run pre-commit run --all-files

build-zip:
	poetry run python scripts/build_addon.py

release-prepare:
	@if [ -z "$(VERSION)" ]; then \
		echo "Usage: make release-prepare VERSION=MAJOR.MINOR.PATCH[-rc.N]"; \
		exit 1; \
	fi
	poetry run python scripts/release.py prepare --version "$(VERSION)"
