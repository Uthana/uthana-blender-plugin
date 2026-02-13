#!/usr/bin/env python3
"""Build a Blender add-on zip with vendored runtime dependencies."""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
PYPROJECT_FILE = ROOT_DIR / "pyproject.toml"
BUILD_DIR = ROOT_DIR / "build" / "addon_stage"
DIST_DIR = ROOT_DIR / "dist"
ADDON_MODULE_NAME = "uthana"
VERSION_LABEL_PATTERN = r"^\d+\.\d+\.\d+(?:-rc\.\d+)?$"


def read_bl_info_version(init_file: Path) -> str:
    """Read version tuple from bl_info inside src/__init__.py."""
    module = ast.parse(init_file.read_text(encoding="utf-8"), filename=str(init_file))
    for statement in module.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name) and target.id == "bl_info":
                    value = ast.literal_eval(statement.value)
                    version_tuple = value.get("version")
                    if not isinstance(version_tuple, tuple):
                        raise ValueError("bl_info['version'] is missing or invalid")
                    return ".".join(str(part) for part in version_tuple)
    raise ValueError("Could not find bl_info assignment in src/__init__.py")


def read_runtime_packages(pyproject_file: Path) -> list[str]:
    """Load runtime dependencies from Poetry, excluding Python itself."""
    data = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))
    dependencies = data["tool"]["poetry"]["dependencies"]
    return [name for name in dependencies if name.lower() != "python"]


def stage_addon_source(stage_root: Path) -> None:
    if stage_root.exists():
        shutil.rmtree(stage_root)
    shutil.copytree(SRC_DIR, stage_root)


def vendor_dependencies(target_dir: Path, package_names: list[str]) -> None:
    if not package_names:
        return
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--target",
        str(target_dir),
        *package_names,
    ]
    subprocess.run(cmd, check=True)


def create_zip(stage_root: Path, version: str) -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = DIST_DIR / f"{ADDON_MODULE_NAME}-{version}.zip"
    if archive_path.exists():
        archive_path.unlink()

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in stage_root.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(BUILD_DIR)
                archive.write(file_path, arcname)
    return archive_path


def resolve_version_label(base_version: str) -> str:
    version_label = os.getenv("UTHANA_BUILD_VERSION_LABEL", base_version).strip()
    if not version_label:
        raise ValueError("UTHANA_BUILD_VERSION_LABEL cannot be empty")
    if not re.fullmatch(VERSION_LABEL_PATTERN, version_label):
        raise ValueError(
            "Version label must match MAJOR.MINOR.PATCH or MAJOR.MINOR.PATCH-rc.N "
            f"(received: {version_label!r})"
        )
    version_base = version_label.split("-", maxsplit=1)[0]
    if version_base != base_version:
        raise ValueError(
            "Version label base must match bl_info version "
            f"(bl_info={base_version}, label={version_label})"
        )
    return version_label


def main() -> None:
    if not SRC_DIR.exists():
        raise FileNotFoundError(f"Missing source directory: {SRC_DIR}")

    version = read_bl_info_version(SRC_DIR / "__init__.py")
    version_label = resolve_version_label(version)
    runtime_packages = read_runtime_packages(PYPROJECT_FILE)

    addon_stage_root = BUILD_DIR / ADDON_MODULE_NAME
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    stage_addon_source(addon_stage_root)
    vendor_dependencies(addon_stage_root, runtime_packages)
    archive_path = create_zip(addon_stage_root, version_label)

    print(f"Built add-on zip: {archive_path}")
    print(f"Vendored dependencies: {', '.join(runtime_packages) if runtime_packages else '(none)'}")


if __name__ == "__main__":
    main()
