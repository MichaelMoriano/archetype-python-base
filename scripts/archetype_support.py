"""Source-checkout compatibility exports for the archive builder."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/archetype_cli/src"))

from institutional_archetype_cli.support import (
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

__all__ = [
    "ARCHETYPE_ARCHIVE_NAME",
    "CONTEXT",
    "GENERATOR_VERSION",
    "PACKAGE_TOKEN",
    "PROJECT_ROOT",
    "TEMPLATE_ID",
    "ArchetypeError",
    "digest",
    "json_bytes",
    "nonblank_path",
    "validate_archive_name",
    "version",
]
