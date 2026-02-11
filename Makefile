.PHONY: install lint format typecheck precommit-install precommit build-zip

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
