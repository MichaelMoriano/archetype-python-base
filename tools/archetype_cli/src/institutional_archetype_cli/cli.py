"""Generate and validate a pinned institutional service before creating its Git baseline."""

import argparse
import base64
import ctypes
import errno
import importlib
import importlib.metadata
import io
import ipaddress
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx

from institutional_archetype_cli import __version__
from institutional_archetype_cli.support import (
    CONTEXT,
    GENERATOR_VERSION,
    MAX_ARCHIVE,
    MAX_EXPANDED,
    PACKAGE_TOKEN,
    PROJECT_ROOT,
    RESERVED,
    TEMPLATE_ID,
    ArchetypeError,
    destination,
    digest,
    environment_default,
    json_bytes,
    names,
    nonblank_path,
    version,
)

DEFAULT_NEXUS = "http://localhost:8082/repository/python-archetypes/"
SCRATCH_PREFIX = "archetype-generation-"
PROMOTION_UNAVAILABLE = "Atomic no-clobber promotion is unavailable on this platform or filesystem."
SAFE_CHILD_ENVIRONMENT = frozenset(
    {
        # Execution, home/config discovery, locale and temporary-directory paths.
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "COMSPEC",
        "HOME",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "LANG",
        "LANGUAGE",
        "LC_ALL",
        "LC_CTYPE",
        "TEMP",
        "TMP",
        "TMPDIR",
        # Storage settings only, never offline, index/auth or validation-bypass flags.
        "UV_CACHE_DIR",
        "UV_PYTHON_INSTALL_DIR",
        "RUFF_CACHE_DIR",
        "MYPY_CACHE_DIR",
        # Public Git identity; normal config discovery and hooks remain enabled.
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_AUTHOR_DATE",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "GIT_COMMITTER_DATE",
    }
)


def nexus_template_path() -> str:
    """Require a relative Raw path before contacting Nexus; never echo input."""
    value = os.environ.get("ARCHETYPE_NEXUS_TEMPLATE_PATH", "")
    if not value.strip():
        raise ArchetypeError(
            "Missing configuration: set ARCHETYPE_NEXUS_TEMPLATE_PATH "
            "to the relative template directory (e.g. python-base)."
        )
    if len(value) > 512 or any(
        part in ("", ".", "..") or not re.fullmatch(r"[A-Za-z0-9_.-]+", part)
        for part in value.split("/")
    ):
        raise ArchetypeError(
            "Invalid configuration: ARCHETYPE_NEXUS_TEMPLATE_PATH must be a relative "
            "slash-separated path with letters, digits, dots, underscores or hyphens; "
            "no empty, '.' or '..' segments, URLs or escapes."
        )
    return value


def remote_url(base: str, template_version: str) -> str:
    template_path = nexus_template_path()
    try:
        parsed = urlsplit(base)
        host = parsed.hostname or ""
        loopback = host == "localhost"
        if not loopback:
            with suppress(ValueError):
                loopback = ipaddress.ip_address(host).is_loopback
        if (
            parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or not host
            or (parsed.scheme != "https" and not (parsed.scheme == "http" and loopback))
        ):
            raise ValueError
        _ = parsed.port
    except ValueError as exc:
        raise ArchetypeError(
            "Nexus requires HTTPS (HTTP is allowed only on loopback), no URL credentials."
        ) from exc
    return base.rstrip("/") + f"/{template_path}/{template_version}/archetype.zip"


def download(url: str, limit: int, purpose: str = "Template download") -> bytes:
    username = os.environ.get("NEXUS_USERNAME", "")
    token = os.environ.get("NEXUS_TOKEN", "")
    headers = {"Accept-Encoding": "identity"}
    if bool(username) != bool(token):
        raise ArchetypeError("Set both NEXUS_USERNAME and NEXUS_TOKEN, or neither.")
    if token:
        encoded = base64.b64encode(f"{username}:{token}".encode()).decode("ascii")
        headers["Authorization"] = "Basic " + encoded
    try:
        # No proxy credentials, redirects, cookie persistence or response bodies in diagnostics.
        with (
            httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client,
            client.stream("GET", url, headers=headers) as response,
        ):
            if response.status_code != 200:
                raise ArchetypeError(
                    f"{purpose} failed (HTTP {response.status_code}); "
                    "check Nexus authentication, permissions and repository path."
                )
            if response.headers.get("content-encoding", "identity") != "identity":
                raise ArchetypeError("Compressed HTTP responses are not accepted.")
            result = bytearray()
            for chunk in response.iter_bytes():
                if len(result) + len(chunk) > limit:
                    raise ArchetypeError("Template download exceeds the size limit.")
                result.extend(chunk)
            return bytes(result)
    except httpx.HTTPError as exc:
        raise ArchetypeError(f"{purpose} failed (transport error or timeout).") from exc


def published_versions(base: str) -> list[str]:
    """List complete Raw template pairs, never trusting returned download URLs."""
    template_path = nexus_template_path()
    remote_url(base, "0.0.0")  # Reuse the download origin/security guard.
    parsed = urlsplit(base)
    context, separator, repository = parsed.path.rstrip("/").rpartition("/repository/")
    if (
        not separator
        or not re.fullmatch(r"[A-Za-z0-9_.-]+", repository)
        or repository in (".", "..")
        or any(
            not re.fullmatch(r"[A-Za-z0-9_~.-]+", part) or part in (".", "..")
            for part in context.split("/")[1:]
        )
    ):
        raise ArchetypeError("Nexus discovery requires a Raw base ending /repository/<name>/.")
    endpoint = f"{parsed.scheme}://{parsed.netloc}{context}/service/rest/v1/assets"
    token: str | None = None
    seen: set[str] = set()
    pairs: dict[str, set[str]] = {}
    asset_count = 0
    response_bytes = 0
    for _ in range(100):
        query = {"repository": repository}
        if token is not None:
            query["continuationToken"] = token
        raw = download(endpoint + "?" + urlencode(query), 4 * 1024 * 1024, "Nexus asset listing")
        response_bytes += len(raw)
        if response_bytes > 16 * 1024 * 1024:
            raise ArchetypeError("Nexus asset listing exceeds the total size limit.")
        try:
            page = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise ArchetypeError("Nexus asset listing returned malformed JSON.") from exc
        if not isinstance(page, dict) or not isinstance(page.get("items"), list):
            raise ArchetypeError("Nexus asset listing returned a malformed page.")
        if "continuationToken" not in page:
            raise ArchetypeError("Nexus asset listing omitted its pagination state.")
        for asset in page["items"]:
            asset_count += 1
            if asset_count > 100_000:
                raise ArchetypeError("Nexus asset listing exceeds the asset limit.")
            if not isinstance(asset, dict) or not isinstance(asset.get("path"), str):
                raise ArchetypeError("Nexus asset listing returned a malformed asset.")
            if asset.get("repository") != repository:
                continue
            match = re.fullmatch(
                re.escape(template_path) + r"/([^/]{1,128})/(archetype\.zip(?:\.sha256)?)",
                asset["path"],
            )
            if match is None:
                continue
            candidate, filename = match.groups()
            try:
                version(candidate)
            except ArchetypeError:
                continue
            pairs.setdefault(candidate, set()).add(filename)
        token = page["continuationToken"]
        if token is None:
            complete = [v for v, files in pairs.items() if len(files) == 2]
            if not complete:
                raise ArchetypeError(
                    "Nexus asset listing contains no complete published templates."
                )
            return sorted(complete, key=lambda v: tuple(int(part) for part in v.split(".")))
        if not isinstance(token, str) or not token or len(token) > 2048 or token in seen:
            raise ArchetypeError(
                "Nexus asset listing returned an invalid or repeated continuation token."
            )
        seen.add(token)
    raise ArchetypeError("Nexus asset listing exceeds the page limit.")


def local_template_version(args: argparse.Namespace) -> str:
    data, _ = archive_data(args)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        info = archive.getinfo("manifest.json")
        if info.file_size > 1024 * 1024:
            raise ArchetypeError("Template manifest exceeds the size limit.")
        manifest = json.loads(archive.read(info))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("template_version"), str):
        raise ArchetypeError("Template manifest has no valid version.")
    selected = version(manifest["template_version"])
    checked_members(data, selected)
    return selected


def expected_hash(value: str) -> str:
    # Accept only our sidecar's conventional format, never arbitrary filenames or extra lines.
    if not re.fullmatch(r"[0-9a-fA-F]{64}(?:  archetype\.zip)?\s*", value):
        raise ArchetypeError("Invalid SHA256 digest or sidecar.")
    return value[:64].lower()


def archive_data(args: argparse.Namespace) -> tuple[bytes, str]:
    if args.archive:
        archive = Path(args.archive)
        if archive.stat().st_size > MAX_ARCHIVE:
            raise ArchetypeError("Template archive exceeds the size limit.")
        data = archive.read_bytes()
        sidecar = archive.with_suffix(archive.suffix + ".sha256")
        if sidecar.stat().st_size > 256:
            raise ArchetypeError("Invalid SHA256 digest or sidecar.")
        expected = expected_hash(sidecar.read_text(encoding="ascii"))
    else:
        url = remote_url(args.nexus_url, args.template_version)
        expected = expected_hash(download(url + ".sha256", 256).decode("ascii"))
        data = download(url, MAX_ARCHIVE)
    actual = digest(data)
    if actual != expected:
        raise ArchetypeError("Template SHA256 mismatch.")
    return data, actual


def checked_members(data: bytes, template_version: str) -> dict[str, bytes]:
    """Validate the entire ZIP before any extraction or destination write."""
    entries: dict[str, bytes] = {}
    seen: set[str] = set()
    total = 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if len(archive.infolist()) > 5000:
            raise ArchetypeError("Too many archive entries.")
        for info in archive.infolist():
            name = info.filename
            safe = name.replace(PROJECT_ROOT, "project").replace(PACKAGE_TOKEN, "package")
            parts = safe.split("/")
            if (
                info.is_dir()
                or info.flag_bits & 1
                or stat.S_ISLNK(info.external_attr >> 16)
                or "\\" in name
                or "\x00" in name
                or any(
                    part in ("", ".", "..")
                    or part.lower() in (".git", ".env", "hooks")
                    or part.split(".")[0].lower() in RESERVED
                    or part.endswith((".", " "))
                    or not re.fullmatch(r"[a-zA-Z0-9_.-]+", part)
                    for part in parts
                )
                or (
                    name not in ("manifest.json", "cookiecutter.json")
                    and not name.startswith(PROJECT_ROOT + "/")
                )
                or safe.lower() in seen
            ):
                raise ArchetypeError("Unsafe template archive entry.")
            seen.add(safe.lower())
            total += info.file_size
            if total > MAX_EXPANDED:
                raise ArchetypeError("Expanded template exceeds the size limit.")
            entries[name] = archive.read(info)
    context = json.loads(entries.get("cookiecutter.json", b"null"))
    legacy_context = {key: value for key, value in CONTEXT.items() if key != "archetype_version"}
    if context != CONTEXT and context != legacy_context:
        raise ArchetypeError("Unsupported Cookiecutter context or extensions.")
    manifest = json.loads(entries.get("manifest.json", b"null"))
    if not isinstance(manifest, dict) or (
        manifest.get("template_id") != TEMPLATE_ID
        or manifest.get("template_version") != template_version
        or manifest.get("generator_version") != GENERATOR_VERSION
        or manifest.get("files")
        != {name: digest(content) for name, content in entries.items() if name != "manifest.json"}
    ):
        raise ArchetypeError("Template manifest does not match the pinned version and contents.")
    if not any(name.startswith(PROJECT_ROOT + "/src/") for name in entries):
        raise ArchetypeError("Template contains no service source.")
    return entries


def run(command: list[str], directory: Path, environment: dict[str, str]) -> None:
    result = subprocess.run(
        command, cwd=directory, env=environment, capture_output=True, text=True, check=False
    )
    if result.returncode:
        # Trusted templates execute tests, but arbitrary output can still contain secrets.
        raise ArchetypeError(
            f"Local step failed: {command[0]} {command[1]} (exit {result.returncode})."
        )


def local_environment(project: Path, validation_environment: Path | None = None) -> dict[str, str]:
    # Default-deny inheritance: unknown credential names must not reach checks or
    # Git hooks. This reduces exposure; trusted template execution is not sandboxed.
    environment = {key: os.environ[key] for key in SAFE_CHILD_ENVIRONMENT if key in os.environ}
    environment["COVERAGE_FILE"] = str(project / ".coverage")
    if validation_environment is not None:
        environment["UV_PROJECT_ENVIRONMENT"] = str(validation_environment)
    environment["PYTHONPATH"] = str(project / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    return environment


def validate(project: Path) -> None:
    # Virtual environments contain absolute editable/launcher paths and cannot be
    # relocated with the service. Keep this disposable environment in owned scratch.
    environment = local_environment(project, project.parents[1] / "validation-venv")
    run(["uv", "lock"], project, environment)
    prefix = ["uv", "run", "--locked"]
    for tool in (
        ["ruff", "format", "."],
        ["ruff", "check", "."],
        ["ruff", "format", "--check", "."],
        ["mypy"],
        ["pytest", "--cov", "--cov-report=term-missing", "--cov-report=xml:coverage.xml", "-q"],
    ):
        run([*prefix, *tool], project, environment)


def git_baseline(project: Path, branch: str) -> None:
    environment = local_environment(project)
    run(["git", "init", "--initial-branch", "main"], project, environment)
    remotes = subprocess.run(
        ["git", "remote"], cwd=project, env=environment, capture_output=True, check=True
    )
    if remotes.stdout:
        raise ArchetypeError("Git initialization inherited an unexpected remote.")
    # Respect the user's existing Git identity and hooks; never write configuration or remotes.
    run(["git", "var", "GIT_AUTHOR_IDENT"], project, environment)
    run(["git", "add", "--", "."], project, environment)
    tracked = (
        subprocess.run(
            ["git", "diff", "--cached", "--name-only", "-z"],
            cwd=project,
            env=environment,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .split("\0")
    )
    if any(
        part in (".env", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache")
        for name in tracked
        for part in name.split("/")
    ):
        raise ArchetypeError("Git baseline would include secrets or generated caches.")
    run(["git", "commit", "-m", "feat: initialize generated service"], project, environment)
    if branch != "main":
        run(["git", "switch", "-c", branch], project, environment)
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project,
        env=environment,
        capture_output=True,
        check=True,
    )
    if result.stdout:
        raise ArchetypeError("Generated Git baseline is not clean.")


def promote(project: Path, target: Path) -> None:
    """Atomically move the staged service without replacing any destination entry.

    Windows rename refuses existing entries. Linux must provide libc renameat2
    and filesystem RENAME_NOREPLACE support. Other platforms fail closed; plain
    POSIX rename, copy-overwrite and precheck-only fallbacks are never used.
    """
    try:
        if sys.platform == "win32":
            os.rename(project, target)
        elif sys.platform == "linux":
            try:
                renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
            except AttributeError as exc:
                raise ArchetypeError(PROMOTION_UNAVAILABLE) from exc
            renameat2.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            ]
            renameat2.restype = ctypes.c_int
            # AT_FDCWD=-100, RENAME_NOREPLACE=1: the kernel checks and renames
            # together, including when a competitor creates an empty directory.
            if renameat2(-100, os.fsencode(project), -100, os.fsencode(target), 1) != 0:
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error))
        else:
            raise ArchetypeError(PROMOTION_UNAVAILABLE)
    except OSError as exc:
        if exc.errno in (errno.EEXIST, errno.ENOTEMPTY):
            raise ArchetypeError("Destination already exists.") from exc
        if exc.errno in (errno.ENOSYS, errno.EINVAL, errno.ENOTSUP):
            raise ArchetypeError(PROMOTION_UNAVAILABLE) from exc
        raise ArchetypeError(
            "Atomic no-clobber promotion failed; staged service retained."
        ) from exc


def generate(args: argparse.Namespace) -> Path:
    project_name, package_name = names(args.name)
    version(args.project_version)
    version(args.template_version)
    target = destination(args.output_dir, project_name)
    if (
        args.branch.startswith("-")
        or subprocess.run(
            ["git", "check-ref-format", "--branch", args.branch],
            capture_output=True,
            check=False,
        ).returncode
    ):
        raise ArchetypeError("Invalid Git branch name.")
    data, archive_hash = archive_data(args)
    entries = checked_members(data, args.template_version)
    manifest = json.loads(entries["manifest.json"])
    # A sibling scratch directory guarantees same-filesystem atomic promotion.
    # destination() has already rejected workspace/project ancestors and symlinks.
    scratch = Path(tempfile.mkdtemp(prefix=SCRATCH_PREFIX, dir=target.parent))
    # Retain our scratch, including failure evidence; never remove a user's directory.
    print(f"Scratch: {scratch}", file=sys.stderr)
    template = scratch / "template"
    for name, content in entries.items():
        path = template / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    answers = {
        "project_name": project_name,
        "package_name": package_name,
        "project_version": args.project_version,
        "archetype_version": manifest["template_version"],
        # Cookiecutter also renders context values as Jinja. TOML Unicode escapes
        # preserve braces without interpreting a user's description as a template.
        # Core package metadata requires a single-line summary. Provenance below
        # retains the original description, including its line breaks.
        "description_literal": json.dumps(
            args.description.replace("\r", " ").replace("\n", " "), ensure_ascii=False
        )
        .replace("{", "\\u007b")
        .replace("}", "\\u007d"),
    }
    cookiecutter: Any = importlib.import_module("cookiecutter.main").cookiecutter
    rendered = cookiecutter(
        str(template),
        no_input=True,
        extra_context=answers,
        accept_hooks=False,
        default_config={"replay_dir": str(scratch / "replay")},
        output_dir=str(scratch / "rendered"),
        keep_project_on_failure=True,
    )
    project = Path(rendered)
    if project.resolve() != (scratch / "rendered" / project_name).resolve():
        raise ArchetypeError("Rendered project is outside the staging boundary.")
    provenance = {
        "template_id": TEMPLATE_ID,
        "template_version": args.template_version,
        "template_sha256": archive_hash,
        "generator_version": __version__,
        "cookiecutter_version": importlib.metadata.version("cookiecutter"),
        "answers": {
            **{key: value for key, value in answers.items() if key != "description_literal"},
            "description": args.description,
        },
        "branch": args.branch,
        "validation": "uv",
    }
    (project / ".archetype-provenance.json").write_bytes(json_bytes(provenance))
    validate(project)
    git_baseline(project, args.branch)
    # The precheck keeps existing ancestor validation; promote() enforces no-clobber
    # atomically even if another creator wins immediately after this check.
    destination(args.output_dir, project_name)
    promote(project, target)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Validation always uses uv with network access allowed. "
            "Git initialization and the initial main commit are required. "
            "The template ZIP must have an accompanying .sha256 file."
        ),
    )
    parser.add_argument("--name", help="Institutional name, e.g. gen_ai_demo or gen-agent-rrhh")
    parser.add_argument(
        "--branch",
        default=None,
        help="Work branch after the initial main commit; prompt when omitted (Enter: main)",
    )
    parser.add_argument(
        "--project-version", default="0.1.0", help="Independent service MAJOR.MINOR.PATCH"
    )
    parser.add_argument(
        "--template-version",
        default=None,
        help="Pinned MAJOR.MINOR.PATCH; omitted: discover/prompt latest published version",
    )
    parser.add_argument(
        "--description",
        default=None,
        help="Nonsecret description, preserved verbatim; prompt with generic default when omitted",
    )
    parser.add_argument(
        "--output-dir",
        type=nonblank_path,
        default=Path.cwd(),
        help="Existing non-project parent; default: the invocation directory",
    )
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--archive",
        type=Path,
        help="Local ZIP with mandatory adjacent .sha256 file (otherwise download from Nexus)",
    )
    source_group.add_argument(
        "--nexus-url",
        default=environment_default("ARCHETYPE_NEXUS_URL", DEFAULT_NEXUS),
        help=(
            "Nexus Raw base; default: ARCHETYPE_NEXUS_URL or loopback Nexus; "
            "requires ARCHETYPE_NEXUS_TEMPLATE_PATH; excludes --archive"
        ),
    )
    args = parser.parse_args(argv)
    try:
        if not args.archive:
            nexus_template_path()
        if args.name is None:
            args.name = input("Project name (e.g. gen_ai_demo): ").strip()
        if args.template_version is None:
            available = (
                [local_template_version(args)]
                if args.archive
                else published_versions(args.nexus_url)
            )
            latest = available[-1]
            label = "Archive version" if args.archive else "Latest available archetype version"
            print(f"{label}: {latest}")
            args.template_version = input(f"Archetype version [{latest}]: ").strip() or latest
            version(args.template_version)
            if args.template_version not in available:
                raise ArchetypeError(
                    "Selected archetype version is not available from this source."
                )
        if args.branch is None:
            args.branch = input("Work branch [main]: ").strip() or "main"
        if args.description is None:
            default_description = "Generated institutional Python service"
            args.description = (
                input(f"Description [{default_description}]: ") or default_description
            )
        target = generate(args)
    except ArchetypeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError, EOFError, zipfile.BadZipFile, subprocess.SubprocessError):
        print(
            "Error: Generation failed; destination was not promoted. "
            "Check inputs and local tooling.",
            file=sys.stderr,
        )
        return 2
    except Exception:
        # Cookiecutter exceptions can contain template values; never echo them.
        print(
            "Error: Template rendering or local validation failed; destination was not promoted.",
            file=sys.stderr,
        )
        return 2
    print(f"Created {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
