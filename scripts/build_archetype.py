"""Build a deterministic, curated Cookiecutter archive from this runnable service."""

import argparse
import json
import sys
import tomllib
import zipfile
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.archetype_support import (
    ARCHETYPE_ARCHIVE_NAME,
    CONTEXT,
    GENERATOR_VERSION,
    PACKAGE_TOKEN,
    PROJECT_ROOT,
    TEMPLATE_ID,
    ArchetypeError,
    digest,
    json_bytes,
    nonblank_path,
    validate_archive_name,
    version,
)

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ".gitignore",
    ".dockerignore",
    ".python-version",
    "Dockerfile",
    "README.md",
    "pyproject.toml",
    "uv.lock",
    "sonar-project.properties",
    "docs/ARCHITECTURE.md",
    "scripts/__init__.py",
    "scripts/audit_dependencies.py",
    "scripts/check.py",
    "scripts/format.ps1",
    "scripts/validate.ps1",
    "tests/__init__.py",
    "tests/settings_helpers.py",
)
DIRECTORIES = ("src/python_ai_service", "tests/unit")
ENV_EXAMPLE = """APP_NAME={{cookiecutter.project_name}}
APP_ENVIRONMENT=local
GEN_SECURITY_BASE_URL=http://localhost:8080
GEN_SECURITY_USE_BASIC_AUTH=false
GEN_SECURITY_USERNAME=
GEN_SECURITY_PASSWORD=
SONAR_HOST_URL=
SONAR_TOKEN=
NVD_API_KEY=
"""


def template_text(path: str, text: str, source_version: str) -> str:
    """Only the service namespace and explicitly owned metadata are parameterized."""
    text = text.replace("python_ai_service", PACKAGE_TOKEN).replace(
        "python-ai-service", "{{cookiecutter.project_name}}"
    )
    if path == "pyproject.toml":
        metadata = tomllib.loads(text)["project"]
        text = (
            text.replace(
                f"name = {json.dumps(metadata['name'])}",
                'name = "{{cookiecutter.project_name}}"',
                1,
            )
            .replace(
                f'version = "{source_version}"',
                'version = "{{cookiecutter.project_version}}"',
                1,
            )
            .replace(
                "description = " + json.dumps(metadata["description"], ensure_ascii=False),
                "description = {{cookiecutter.description_literal}}",
                1,
            )
        )
        # Scaffolding is not a development dependency of generated services.
        text = (
            "\n".join(
                line for line in text.splitlines() if not line.strip().startswith('"cookiecutter')
            )
            + "\n"
        )
        text = text.replace('mypy_path = "tools/archetype_cli/src"\n', "").replace(
            'files = ["src", "scripts", "tests", "tools/archetype_cli/src"]',
            'files = ["src", "scripts", "tests"]',
        )
    elif path == "src/python_ai_service/__init__.py":
        text = text.replace(f'"{source_version}"', '"{{cookiecutter.project_version}}"')
    elif path == "sonar-project.properties":
        text = (
            "\n".join(
                "sonar.projectKey={{cookiecutter.project_name}}"
                if line.startswith("sonar.projectKey=")
                else "sonar.projectName={{cookiecutter.project_name}}"
                if line.startswith("sonar.projectName=")
                else line
                for line in text.splitlines()
            )
            + "\n"
        )
    elif path == "README.md":
        text = text.replace(
            "# Arquetipo Python Base para Servicios de IA", "# {{cookiecutter.project_name}}", 1
        )
        text = text.replace("gen_ai_demo", PACKAGE_TOKEN).replace(
            "gen-ai-demo", "{{cookiecutter.project_name}}"
        )
        text = text.replace(
            "[guía de distribución](docs/NEXUS_DEVOPS.md)",
            "guía de distribución del repositorio fuente del arquetipo",
        ).replace(
            "[guía del generador](docs/ARCHETYPE.md)",
            "guía del generador en el repositorio fuente del arquetipo",
        )
        text = text.replace(
            "[guía de arquitectura](docs/ARCHITECTURE.md)", "`docs/ARCHITECTURE.md`"
        )
    elif path == "docs/ARCHITECTURE.md":
        text = text.replace(
            "Documentación relacionada: [guía del developer](../README.md),\n"
            "[preparación TI_EDO](NEXUS_DEVOPS.md) y [distribución del arquetipo](ARCHETYPE.md).",
            "Documentación relacionada: [guía del developer](../README.md).\n"
            "Las guías de preparación TI_EDO y distribución están en el repositorio fuente "
            "del arquetipo; no forman parte del servicio generado.",
        )
    # Preserve literal Jinja syntax in the original service; only our tokens render.
    tokens = (
        PACKAGE_TOKEN,
        "{{cookiecutter.project_name}}",
        "{{cookiecutter.project_version}}",
        "{{cookiecutter.archetype_version}}",
        "{{cookiecutter.description_literal}}",
        "{{cookiecutter.repository_nexus}}",
        "{{cookiecutter.cli_name}}",
        "{{cookiecutter.archetype_directory}}",
    )
    for index, token in enumerate(tokens):
        text = text.replace(token, f"ARCHETYPETOKEN{index}END")
    text = "{% raw %}" + text + "{% endraw %}"
    for index, token in enumerate(tokens):
        text = text.replace(f"ARCHETYPETOKEN{index}END", "{% endraw %}" + token + "{% raw %}")
    return text


def build(output: Path, template_version: str) -> Path:
    archive_name = validate_archive_name(ARCHETYPE_ARCHIVE_NAME)
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    paths = [ROOT / name for name in FILES]
    for directory in DIRECTORIES:
        paths.extend(
            path for path in (ROOT / directory).rglob("*.py") if "__pycache__" not in path.parts
        )
    entries = {"cookiecutter.json": json_bytes(CONTEXT)}
    for source in sorted(paths):
        if source.is_symlink() or not source.is_file():
            raise ArchetypeError("A required source file is missing or is a symlink.")
        relative = source.relative_to(ROOT).as_posix()
        target = relative.replace("python_ai_service", PACKAGE_TOKEN)
        entries[f"{PROJECT_ROOT}/{target}"] = template_text(
            relative, source.read_text(encoding="utf-8"), metadata["project"]["version"]
        ).encode()
    entries[f"{PROJECT_ROOT}/.env.example"] = ENV_EXAMPLE.encode()
    entries["manifest.json"] = json_bytes(
        {
            "template_id": TEMPLATE_ID,
            "template_version": template_version,
            "generator_version": GENERATOR_VERSION,
            "files": {name: digest(data) for name, data in sorted(entries.items())},
        }
    )
    output_directory = output / TEMPLATE_ID / template_version
    output_directory.mkdir(parents=True, exist_ok=True)
    archive = output_directory / archive_name
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            handle.writestr(info, data)
    archive.with_name(f"{archive_name}.sha256").write_text(
        f"{digest(archive.read_bytes())}  {archive_name}\n", encoding="ascii"
    )
    return archive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--template-version",
        default=None,
        help="MAJOR.MINOR.PATCH; default: source project version",
    )
    parser.add_argument(
        "--output-dir",
        type=nonblank_path,
        default=ROOT / "dist",
        help="Artifact root; default: the repository dist directory",
    )
    args = parser.parse_args(argv)
    try:
        validate_archive_name(ARCHETYPE_ARCHIVE_NAME)
    except ArchetypeError as error:
        print(f"Error: ARCHETYPE_ARCHIVE_NAME: {error}", file=sys.stderr)
        return 2
    try:
        source_version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
        template_version = (
            args.template_version if args.template_version is not None else source_version
        )
        archive = build(args.output_dir, version(template_version))
    except (ArchetypeError, OSError, ValueError):
        print("Error: Could not build the curated archetype archive.", file=sys.stderr)
        return 2
    print(f"Built {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
