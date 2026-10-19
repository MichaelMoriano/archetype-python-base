"""Audit locked dependencies and fail closed on CVSS >= 7 or incomplete evidence."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

ROOT = Path(__file__).resolve().parents[1]
NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
THRESHOLD = 7.0
CVSS_METRICS = ("cvssMetricV31", "cvssMetricV30", "cvssMetricV40")


class AuditError(Exception):
    """The security check could not obtain complete evidence."""


class NvdLookupError(AuditError):
    """Only controlled diagnostic fields may reach the console or report."""

    def __init__(
        self,
        cve_id: str,
        category: str,
        http_status: int | None = None,
        field: str | None = None,
    ) -> None:
        self.details: dict[str, str | int] = {"cve_id": cve_id, "category": category}
        messages = {
            "http_status": "request rejected; check access, API key and rate limits",
            "timeout": "request timed out; check connectivity and service availability",
            "network": "transport failed; check proxy, TLS trust and network access",
            "invalid_json": "response is not valid JSON; check proxy or upstream content",
            "schema": "response does not match the expected NVD schema",
            "record_missing": "NVD did not return exactly one CVE record",
            "record_mismatch": "NVD returned a mismatched or rejected CVE",
            "missing_score": "no supported CVSS v3/v4 score is available",
        }
        message = f"NVD lookup failed for {cve_id}: {messages[category]}"
        if http_status is not None:
            self.details["http_status"] = http_status
            message += f" (HTTP {http_status})"
        if field:
            self.details["field"] = field
            message += f"; field: {field}"
        super().__init__(message)


class Finding(BaseModel):
    model_config = ConfigDict(strict=True)
    id: str
    aliases: list[str] = Field(default_factory=list)
    fix_versions: list[str] = Field(default_factory=list)


class Dependency(BaseModel):
    model_config = ConfigDict(strict=True)
    name: str
    version: str | None = None
    vulns: list[Finding] | None = None
    skip_reason: str | None = None


class AuditReport(BaseModel):
    model_config = ConfigDict(strict=True)
    dependencies: list[Dependency] = Field(min_length=1)


class CvssData(BaseModel):
    model_config = ConfigDict(strict=True)
    base_score: float = Field(alias="baseScore", ge=0, le=10, allow_inf_nan=False)


class Metric(BaseModel):
    model_config = ConfigDict(strict=True)
    cvss_data: CvssData = Field(alias="cvssData")


class Cve(BaseModel):
    model_config = ConfigDict(strict=True)
    id: str
    status: str = Field(alias="vulnStatus")
    metrics: dict[str, list[Metric]] = Field(default_factory=dict)

    @field_validator("metrics", mode="before")
    @classmethod
    def select_cvss_metrics(cls, value: Any) -> Any:
        """SSVC and future non-CVSS metrics do not share the cvssData contract."""
        if isinstance(value, dict):
            return {key: metric for key, metric in value.items() if key in CVSS_METRICS}
        return value


class CveRecord(BaseModel):
    model_config = ConfigDict(strict=True)
    cve: Cve


class NvdResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    total: int = Field(alias="totalResults")
    vulnerabilities: list[CveRecord]


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    environment = {
        key: value for key, value in os.environ.items() if key not in {"NVD_API_KEY", "SONAR_TOKEN"}
    }
    environment["PYTHONUTF8"] = "1"
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return result


def inventory(path: Path) -> set[tuple[str, Version]]:
    """Check the audit covers all pinned packages applicable to this interpreter."""
    packages: set[tuple[str, Version]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        requirement = Requirement(line)
        pins = list(requirement.specifier)
        if requirement.url or len(pins) != 1 or pins[0].operator != "==":
            raise AuditError("The export contains an unsupported or unpinned dependency.")
        if requirement.marker is None or requirement.marker.evaluate():
            packages.add((canonicalize_name(requirement.name), Version(pins[0].version)))
    if not packages:
        raise AuditError("The dependency inventory is empty.")
    return packages


def collect_dependencies(directory: Path) -> list[Dependency]:
    requirements = directory / "requirements.txt"
    export = run_command(
        [
            "uv",
            "export",
            "--locked",
            "--all-groups",
            "--no-emit-project",
            "--format",
            "requirements.txt",
            "--no-hashes",
            "--no-annotate",
            "--no-header",
            "--output-file",
            str(requirements),
        ]
    )
    if export.returncode != 0:
        raise AuditError("Locked dependency export failed; no audit was approved.")
    expected = inventory(requirements)
    output = directory / "pip-audit.json"
    scan = run_command(
        [
            sys.executable,
            "-m",
            "pip_audit",
            "--requirement",
            str(requirements),
            "--no-deps",
            "--disable-pip",
            "--strict",
            "--aliases=on",
            "--vulnerability-service",
            "pypi",
            "--format",
            "json",
            "--output",
            str(output),
            "--progress-spinner",
            "off",
        ]
    )
    if scan.returncode not in (0, 1):
        raise AuditError("pip-audit could not complete the audit.")
    dependencies = AuditReport.model_validate_json(output.read_text(encoding="utf-8")).dependencies
    actual = set()
    for dependency in dependencies:
        if (
            dependency.skip_reason is not None
            or dependency.version is None
            or dependency.vulns is None
        ):
            raise AuditError("pip-audit skipped or did not resolve a dependency.")
        actual.add((canonicalize_name(dependency.name), Version(dependency.version)))
    if actual != expected:
        raise AuditError("The scanned inventory does not match the locked export.")
    has_findings = any(dependency.vulns for dependency in dependencies)
    if has_findings != (scan.returncode == 1):
        raise AuditError("pip-audit exit code and report disagree.")
    return dependencies


def nvd_score(client: httpx.Client, cve_id: str) -> float:
    try:
        response = client.get(NVD_URL, params={"cveId": cve_id})
        response.raise_for_status()
    except httpx.TimeoutException:
        raise NvdLookupError(cve_id, "timeout") from None
    except httpx.HTTPStatusError as error:
        raise NvdLookupError(cve_id, "http_status", error.response.status_code) from None
    except httpx.RequestError:
        raise NvdLookupError(cve_id, "network") from None
    try:
        payload = NvdResponse.model_validate(response.json())
    except ValidationError as error:
        # Dictionary keys and input values can contain arbitrary remote content.
        safe_fields = {
            "totalResults",
            "vulnerabilities",
            "cve",
            "id",
            "vulnStatus",
            "metrics",
            "cvssMetricV30",
            "cvssMetricV31",
            "cvssMetricV40",
            "cvssData",
            "baseScore",
        }
        location = error.errors(include_input=False, include_context=False, include_url=False)[0][
            "loc"
        ]
        field = (
            ".".join(str(part) for part in location if isinstance(part, int) or part in safe_fields)
            or "response"
        )
        raise NvdLookupError(cve_id, "schema", response.status_code, field) from None
    except ValueError:
        raise NvdLookupError(cve_id, "invalid_json", response.status_code) from None
    if payload.total != 1 or len(payload.vulnerabilities) != 1:
        raise NvdLookupError(cve_id, "record_missing", response.status_code)
    cve = payload.vulnerabilities[0].cve
    if cve.id != cve_id or cve.status == "Rejected":
        raise NvdLookupError(cve_id, "record_mismatch", response.status_code)
    scores = [
        metric.cvss_data.base_score for key in CVSS_METRICS for metric in cve.metrics.get(key, [])
    ]
    if not scores:
        raise NvdLookupError(cve_id, "missing_score", response.status_code)
    # Conservative policy: the highest published v3/v4 base score wins.
    return max(scores)


def assess(
    dependencies: list[Dependency], client: httpx.Client, delay: float
) -> list[dict[str, Any]]:
    findings = []
    cache: dict[str, float] = {}
    for dependency in dependencies:
        for vulnerability in dependency.vulns or []:
            cves = sorted(
                {
                    value
                    for value in [vulnerability.id, *vulnerability.aliases]
                    if re.fullmatch(r"CVE-\d{4}-\d{4,}", value)
                }
            )
            if not cves:
                raise AuditError("A finding has no CVE alias; its CVSS cannot be verified.")
            for cve in cves:
                if cve not in cache:
                    if cache:
                        time.sleep(delay)
                    cache[cve] = nvd_score(client, cve)
            score = max(cache[cve] for cve in cves)
            findings.append(
                {
                    "package": dependency.name,
                    "version": dependency.version,
                    "id": vulnerability.id,
                    "cves": cves,
                    "cvss": score,
                    "cvss_by_cve": {cve: cache[cve] for cve in cves},
                    "severity": "CRITICAL"
                    if score >= 9
                    else "HIGH"
                    if score >= 7
                    else "BELOW_HIGH",
                    "fix_versions": vulnerability.fix_versions,
                    "blocked": score >= THRESHOLD,
                }
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=ROOT / "build" / "security")
    args = parser.parse_args(argv)
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "incomplete",
        "threshold": THRESHOLD,
        "source": "NVD CVSS v3/v4 maximum",
        "scope": "runtime and all dependency groups; current Python/platform markers",
        "findings": [],
    }
    try:
        args.report_dir.mkdir(parents=True, exist_ok=True)
        report_path = args.report_dir / "dependency-audit.json"
        raw_path = args.report_dir / "pip-audit.json"
        # Invalidate an earlier PASS before starting any external operation.
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        raw_path.write_text('{"status":"incomplete"}', encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="dependency-audit-") as temporary:
            dependencies = collect_dependencies(Path(temporary))
        report["packages_scanned"] = len(dependencies)
        raw_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "dependencies": [dependency.model_dump() for dependency in dependencies],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        api_key = os.environ.get("NVD_API_KEY")
        headers = {"apiKey": api_key} if api_key else {}
        with httpx.Client(headers=headers, timeout=15, follow_redirects=False) as client:
            report["findings"] = assess(dependencies, client, 0.6 if api_key else 6.0)
        blocked = any(finding["blocked"] for finding in report["findings"])
        report["status"] = "blocked" if blocked else "passed"
        for finding in report["findings"]:
            # Escape control characters from external identifiers before printing.
            print(json.dumps(finding, ensure_ascii=True))
        print(f"Dependency audit {report['status']}; {len(dependencies)} packages scanned.")
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 1 if blocked else 0
    except (
        AuditError,
        httpx.HTTPError,
        ValueError,
        KeyError,
        TypeError,
        OSError,
        subprocess.SubprocessError,
    ) as error:
        # Never print subprocess output, API responses, URLs with credentials or the NVD key.
        report["status"] = "incomplete"
        if isinstance(error, NvdLookupError):
            report["error_context"] = error.details
        report["error"] = (
            str(error)
            if isinstance(error, AuditError)
            else ("Audit incomplete: check export, advisory access, inventory and CVSS evidence.")
        )
        print(report["error"])
        try:
            (args.report_dir / "dependency-audit.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
        except OSError:
            print("Could not write the audit report.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
