"""Shared, deliberately narrow archive format and console safety rules."""

import argparse
import hashlib
import json
import keyword
import os
import re
from pathlib import Path
from typing import Any

TEMPLATE_ID = "python-service-archetype"

GENERATOR_VERSION = "0.1.0"
PROJECT_ROOT = "{{cookiecutter.project_name}}"
PACKAGE_TOKEN = "{{cookiecutter.package_name}}"
MAX_ARCHIVE = 32 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
CONTEXT = {
    "project_name": "gen-ai-service",
    "package_name": "gen_ai_service",
    "project_version": "0.1.0",
    "archetype_version": "",
    "archetype_directory": "python-service-archetype",
    "description_literal": '"Generated Python service"',
    "repository_nexus": "python-archetypes",
    "cli_name": "institutional_python_cli-0.1.1-py3-none-any.whl",
}
RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    "clock$",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

# The name of the archetype archive file.
ARCHETYPE_ARCHIVE_NAME = "archetype.zip"


class ArchetypeError(Exception):
    """A safe, nonsecret diagnostic suitable for console output."""


def validate_archive_name(value: str) -> str:
    """Accept a portable ZIP basename, never a path or a URL."""
    if (
        not isinstance(value, str)
        or len(value) > 128
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*\.zip", value)
        or value[:-4].lower() in RESERVED
    ):
        raise ArchetypeError(
            "Invalid archive name: use at most 128 ASCII characters, starting with a letter "
            "or digit, followed by letters, digits, underscores or hyphens and ending in .zip; "
            "paths, URLs and reserved Windows names are not allowed."
        )
    return value


def environment_default(name: str, fallback: str | None = None) -> str | None:
    """Read a process default per invocation, treating only blank values as unset."""
    value = os.environ.get(name)
    return value if value is not None and value.strip() else fallback


def nonblank_path(value: str) -> Path:
    """Reject explicit empty paths before Path would normalize them to the cwd."""
    if not value.strip():
        raise argparse.ArgumentTypeError("Directory path must not be blank.")
    return Path(value)


def version(value: str) -> str:
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", value):
        raise ArchetypeError("Version must have the form MAJOR.MINOR.PATCH.")
    return value


def names(value: str) -> tuple[str, str]:
    normalized = value.replace("_", "-")
    package = normalized.replace("-", "_")
    if (
        len(value) > 80
        or not re.fullmatch(r"[a-z][a-z0-9]*(?:[-_][a-z0-9]+)+", value)
        or any(part in RESERVED for part in normalized.split("-"))
        or keyword.iskeyword(package)
    ):
        raise ArchetypeError("Invalid institutional project name.")
    return normalized, package


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode()


def destination(parent: Path, name: str) -> Path:
    """Never nest a generated repository in an existing project or overwrite an entry."""
    if not parent.is_dir() or parent.is_symlink():
        raise ArchetypeError("Output directory must already exist and not be a symlink.")
    target = parent.resolve() / name
    if target.exists() or target.is_symlink():
        raise ArchetypeError("Destination already exists.")
    for ancestor in (parent.resolve(), *parent.resolve().parents):
        if any((ancestor / marker).exists() for marker in (".git", "pyproject.toml")):
            raise ArchetypeError("Output directory is inside an existing project.")
    return target
