"""Run mandatory quality, dependency-security and Sonar gates in order."""

import argparse
import ipaddress
import os
import re
import subprocess
import sys
import tempfile
from contextlib import suppress
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[1]


def sonar_base_url(value: str) -> str:
    """Never send the diagnostic token to metadata URLs or insecure remote hosts."""
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    loopback = host == "localhost"
    if not loopback:
        with suppress(ValueError):
            loopback = ipaddress.ip_address(host).is_loopback
    if (
        not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or (parsed.scheme != "https" and not (parsed.scheme == "http" and loopback))
    ):
        raise ValueError("Unsafe diagnostic origin")
    _ = parsed.port
    return value.rstrip("/")


def sonar_value(value: object) -> str:
    """Render metric values only, not arbitrary server text or terminal controls."""
    text = str(value)
    return text if re.fullmatch(r"(?:-?\d+(?:\.\d+)?|[A-E])", text) else "unavailable"


def show_sonar_details(metadata_file: Path, environment: dict[str, str]) -> None:
    """Best-effort diagnostics; a failed scanner can never become a successful gate."""
    try:
        base = sonar_base_url(environment["SONAR_HOST_URL"])
        if metadata_file.stat().st_size > 65_536:
            raise ValueError("Oversized metadata")
        metadata = dict(
            line.split("=", 1)
            for line in metadata_file.read_text(encoding="utf-8").splitlines()
            if "=" in line and not line.startswith("#")
        )
        task_id = metadata.get("ceTaskId", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", task_id):
            raise ValueError("Missing analysis task")
        with httpx.Client(
            timeout=15,
            follow_redirects=False,
            trust_env=False,
            headers={"Authorization": f"Bearer {environment['SONAR_TOKEN']}"},
        ) as client:
            response = client.get(f"{base}/api/ce/task", params={"id": task_id})
            response.raise_for_status()
            task = response.json()["task"]
            if task["status"] != "SUCCESS":
                raise ValueError("Analysis not completed")
            analysis_id = task["analysisId"]
            if not isinstance(analysis_id, str) or not re.fullmatch(
                r"[A-Za-z0-9_-]{1,256}", analysis_id
            ):
                raise ValueError("Missing analysis identity")
            response = client.get(
                f"{base}/api/qualitygates/project_status", params={"analysisId": analysis_id}
            )
            response.raise_for_status()
            status = response.json()["projectStatus"]
        if not isinstance(status, dict) or not isinstance(status.get("conditions"), list):
            raise ValueError("Invalid gate response")
        lines = []
        for condition in status["conditions"]:
            if not isinstance(condition, dict):
                raise ValueError("Invalid condition")
            if condition.get("status") != "ERROR":
                continue
            key = condition.get("metricKey", "")
            if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,100}", key):
                raise ValueError("Invalid metric")
            label = {"coverage": "Coverage", "new_coverage": "New code coverage"}.get(key, key)
            unit = "%" if re.search(r"coverage|density|hotspots_reviewed", key) else ""
            actual = sonar_value(condition.get("actualValue"))
            threshold = sonar_value(condition.get("errorThreshold"))
            comparator = condition.get("comparator")
            if not isinstance(comparator, str):
                raise ValueError("Invalid comparator")
            required = {"LT": ">=", "GT": "<="}.get(comparator, "?")
            lines.append(f"- {label}: {actual}{unit}; required {required} {threshold}{unit}")
        print(
            "SonarQube Quality Gate failed conditions:"
            if lines
            else "No failed Quality Gate conditions reported; check scanner output."
        )
        for line in lines:
            print(line.replace(environment["SONAR_TOKEN"], "[redacted]"))
        project_key = metadata.get("projectKey")
        if project_key:
            dashboard = f"{base}/dashboard?id={quote(project_key, safe='')}"
            print("Dashboard: " + dashboard.replace(environment["SONAR_TOKEN"], "[redacted]"))
    except (OSError, ValueError, KeyError, TypeError, httpx.HTTPError, httpx.InvalidURL):
        print(
            "Quality Gate details unavailable; check scanner output, "
            "server access and token permissions."
        )


def run_sonar(command: list[str], environment: dict[str, str]) -> int:
    """Use fresh external metadata so old project analyses cannot supply diagnostics."""
    with tempfile.TemporaryDirectory(prefix="sonar-check-") as directory:
        metadata_file = Path(directory) / "report-task.txt"
        result = subprocess.run(
            [*command, "--sonar-scanner-metadata-filepath", str(metadata_file)],
            cwd=ROOT,
            env=environment,
            check=False,
        )
        if result.returncode:
            show_sonar_details(metadata_file, environment)
        else:
            print("SonarQube analysis and Quality Gate passed.")
        return result.returncode


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    steps = [
        ("Lockfile", ["uv", "lock", "--check"]),
        ("Lint", ["uv", "run", "--locked", "ruff", "check", "."]),
        ("Format", ["uv", "run", "--locked", "ruff", "format", "--check", "."]),
        ("Types", ["uv", "run", "--locked", "mypy"]),
        (
            "Tests",
            [
                "uv",
                "run",
                "--locked",
                "pytest",
                "--cov",
                "--cov-report=term-missing",
                "--cov-report=xml:coverage.xml",
            ],
        ),
        ("Dependencies", [sys.executable, str(ROOT / "scripts" / "audit_dependencies.py")]),
        ("Sonar", ["uv", "run", "--locked", "pysonar", "--sonar-qualitygate-wait"]),
    ]
    for label, command in steps:
        print(f"\n=== {label} ===", flush=True)
        if label == "Sonar" and not all(
            os.environ.get(key, "").strip() for key in ("SONAR_TOKEN", "SONAR_HOST_URL")
        ):
            print("Stopped: configure SONAR_HOST_URL and SONAR_TOKEN before the Sonar step.")
            return 2
        environment = {**os.environ, "PYTHONUTF8": "1"}
        if label != "Sonar":
            environment.pop("SONAR_TOKEN", None)
        if label != "Dependencies":
            environment.pop("NVD_API_KEY", None)
        try:
            if label == "Sonar":
                return_code = run_sonar(command, environment)
            else:
                return_code = subprocess.run(
                    command, cwd=ROOT, env=environment, check=False
                ).returncode
        except OSError:
            print(f"Stopped: could not execute {label}.")
            return 2
        if return_code != 0:
            print(f"Stopped: {label} failed (exit {return_code}). No later step ran.")
            return 1
    print("All required checks passed. No image was published or deployed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
