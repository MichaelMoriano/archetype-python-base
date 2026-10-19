"""Run mandatory quality, dependency-security and Sonar gates in order."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
            result = subprocess.run(command, cwd=ROOT, env=environment, check=False)
        except OSError:
            print(f"Stopped: could not execute {label}.")
            return 2
        if result.returncode != 0:
            print(f"Stopped: {label} failed (exit {result.returncode}). No later step ran.")
            return 1
    print("All required checks passed. No image was published or deployed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
