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
from typing import Any, Literal

import httpx
from cvss import CVSS3, CVSS4
from cvss.exceptions import CVSSError
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

ROOT = Path(__file__).resolve().parents[1]
NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
OSV_URL = "https://api.osv.dev/v1/vulns/"
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


class OsvLookupError(AuditError):
    """Controlled OSV diagnostics, without response content or request credentials."""

    def __init__(self, advisory_id: str, category: str, http_status: int | None = None) -> None:
        self.details: dict[str, str | int] = {
            "source": "OSV",
            "advisory_id": advisory_id,
            "category": category,
        }
        if http_status is not None:
            self.details["http_status"] = http_status
        super().__init__(f"OSV lookup incomplete ({category}); no score was accepted.")


class OsvSeverity(BaseModel):
    model_config = ConfigDict(strict=True)
    type: str
    score: str = Field(max_length=512)


class OsvPackage(BaseModel):
    model_config = ConfigDict(strict=True)
    name: str
    ecosystem: str


class OsvRange(BaseModel):
    model_config = ConfigDict(strict=True)
    type: Literal["ECOSYSTEM", "SEMVER", "GIT"]
    events: list[dict[str, str]] = Field(min_length=1)


class OsvAffected(BaseModel):
    model_config = ConfigDict(strict=True)
    package: OsvPackage
    versions: list[str] = Field(default_factory=list)
    ranges: list[OsvRange] = Field(default_factory=list)
    severity: list[OsvSeverity] = Field(default_factory=list)


class OsvAdvisory(BaseModel):
    model_config = ConfigDict(strict=True)
    id: str
    aliases: list[str] = Field(default_factory=list)
    withdrawn: str | None = None
    affected: list[OsvAffected]
    severity: list[OsvSeverity] = Field(default_factory=list)


def osv_affects(affected: OsvAffected, installed: Version) -> bool:
    # Validate every relevant interval before trusting either ranges or version lists.
    versions = [Version(value) for value in affected.versions]
    matches = installed in versions
    for interval in affected.ranges:
        if interval.type != "ECOSYSTEM":
            continue
        opened = False
        start: Version | None = None
        for event in interval.events:
            if len(event) != 1:
                raise ValueError("Invalid OSV range event")
            kind, value = next(iter(event.items()))
            if kind == "introduced" and not opened:
                opened = True
                start = None if value == "0" else Version(value)
            elif kind in ("fixed", "limit", "last_affected") and opened:
                end = Version(value)
                if start is not None and end < start:
                    raise ValueError("Inverted OSV range")
                if (start is None or installed >= start) and (
                    installed <= end if kind == "last_affected" else installed < end
                ):
                    matches = True
                opened = False
            else:
                raise ValueError("Unsupported OSV range event")
        if opened and (start is None or installed >= start):
            matches = True
    return matches


def osv_vector_score(severity: OsvSeverity) -> dict[str, Any] | None:
    if severity.type == "CVSS_V3" and severity.score.startswith(("CVSS:3.0/", "CVSS:3.1/")):
        calculator: Any = CVSS3
        keys = {"AV", "AC", "PR", "UI", "S", "C", "I", "A"}
    elif severity.type == "CVSS_V4" and severity.score.startswith("CVSS:4.0/"):
        calculator = CVSS4
        keys = {"AV", "AC", "AT", "PR", "UI", "VC", "VI", "VA", "SC", "SI", "SA"}
    elif severity.type not in ("CVSS_V3", "CVSS_V4"):
        return None
    else:
        raise ValueError("CVSS type and vector disagree")
    parts = severity.score.split("/")
    metric_keys = [part.split(":", 1)[0] for part in parts[1:]]
    if len(set(metric_keys)) != len(metric_keys):
        raise ValueError("Duplicate CVSS metrics")
    calculator(severity.score)  # Validate the full vector before extracting base metrics.
    base_vector = "/".join([parts[0], *(p for p in parts[1:] if p.split(":", 1)[0] in keys)])
    score = float(calculator(base_vector).base_score)
    if not 0 <= score <= 10:
        raise ValueError("Invalid CVSS score")
    return {"type": severity.type, "vector": base_vector, "cvss": score}


def osv_score(client: httpx.Client, advisory_id: str, dependency: Dependency) -> dict[str, Any]:
    if not re.fullmatch(
        r"(?:GHSA-[23456789cfghjmpqrvwx]{4}(?:-[23456789cfghjmpqrvwx]{4}){2}|"
        r"PYSEC-\d{4}-\d+|CVE-\d{4}-\d{4,})",
        advisory_id,
    ):
        raise OsvLookupError("unsupported", "unsupported_id")
    try:
        with client.stream("GET", OSV_URL + advisory_id) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_bytes(chunk_size=65_536):
                data.extend(chunk)
                if len(data) > 1_048_576:
                    raise OsvLookupError(advisory_id, "response_too_large")
        advisory = OsvAdvisory.model_validate_json(data)
        if advisory.id != advisory_id or advisory.withdrawn is not None:
            raise OsvLookupError(advisory_id, "record_mismatch_or_withdrawn")
        if dependency.version is None:
            raise OsvLookupError(advisory_id, "missing_package_version")
        matching = [
            item
            for item in advisory.affected
            if item.package.ecosystem == "PyPI"
            and canonicalize_name(item.package.name) == canonicalize_name(dependency.name)
            and osv_affects(item, Version(dependency.version))
        ]
        if not matching:
            raise OsvLookupError(advisory_id, "package_or_version_mismatch")
        severities = [*advisory.severity, *(s for item in matching for s in item.severity)]
        vectors = [result for s in severities if (result := osv_vector_score(s)) is not None]
        if not vectors:
            raise OsvLookupError(advisory_id, "missing_score")
        return {
            "source": "OSV",
            "advisory_id": advisory_id,
            "cvss": max(item["cvss"] for item in vectors),
            "vectors": vectors,
        }
    except httpx.TimeoutException:
        raise OsvLookupError(advisory_id, "timeout") from None
    except httpx.HTTPStatusError as error:
        raise OsvLookupError(advisory_id, "http_status", error.response.status_code) from None
    except httpx.RequestError:
        raise OsvLookupError(advisory_id, "network") from None
    except (ValueError, CVSSError):
        raise OsvLookupError(advisory_id, "invalid_response_or_vector") from None


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
    dependencies: list[Dependency],
    client: httpx.Client,
    delay: float,
    osv_client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    findings = []
    cache: dict[str, float] = {}
    failures: dict[str, NvdLookupError] = {}
    osv_cache: dict[tuple[str, str, str | None], dict[str, Any] | OsvLookupError] = {}

    def lookup(advisory_id: str, dependency: Dependency) -> dict[str, Any] | OsvLookupError:
        key = (advisory_id, canonicalize_name(dependency.name), dependency.version)
        if key not in osv_cache:
            if osv_cache:
                time.sleep(0.2)
            assert osv_client is not None
            try:
                osv_cache[key] = osv_score(osv_client, advisory_id, dependency)
            except OsvLookupError as error:
                osv_cache[key] = error
        return osv_cache[key]

    for dependency in dependencies:
        for vulnerability in dependency.vulns or []:
            cves = sorted(
                {
                    value
                    for value in [vulnerability.id, *vulnerability.aliases]
                    if re.fullmatch(r"CVE-\d{4}-\d{4,}", value)
                }
            )
            errors: list[dict[str, Any]] = []
            if not cves:
                errors.append(
                    {
                        "category": "missing_cve",
                        "message": "A finding has no CVE alias; its CVSS cannot be verified.",
                    }
                )
            for cve in cves:
                if cve not in cache and cve not in failures:
                    if cache or failures:
                        time.sleep(delay)
                    try:
                        cache[cve] = nvd_score(client, cve)
                    except NvdLookupError as error:
                        failures[cve] = error
                if cve in failures:
                    errors.append({**failures[cve].details, "message": str(failures[cve])})
            scores = {cve: cache[cve] for cve in cves if cve in cache}
            evidence: list[dict[str, Any]] = [
                {"source": "NVD", "advisory_id": cve, "cvss": value}
                for cve, value in scores.items()
            ]
            warnings = []
            if errors and osv_client is not None:
                warnings = [{"source": "NVD", **error} for error in errors]
                candidates = (
                    [cve for cve in cves if cve in failures]
                    if cves
                    else sorted(
                        set([vulnerability.id, *vulnerability.aliases]),
                        key=lambda value: (not value.startswith("GHSA-"), value),
                    )[:8]
                )
                for advisory_id in candidates:
                    fallback = lookup(advisory_id, dependency)
                    if isinstance(fallback, OsvLookupError):
                        diagnostic = {**fallback.details, "message": str(fallback)}
                        errors.append(diagnostic)
                        warnings.append(diagnostic)
                    else:
                        evidence.append(fallback)
                        if not cves:
                            errors = []
                            break
                        errors = [error for error in errors if error.get("cve_id") != advisory_id]
            known_max = max((item["cvss"] for item in evidence), default=None)
            score = known_max if not errors else None
            findings.append(
                {
                    "package": dependency.name,
                    "version": dependency.version,
                    "id": vulnerability.id,
                    "aliases": vulnerability.aliases,
                    "cves": cves,
                    "cvss": score,
                    "cvss_by_cve": scores,
                    "score_evidence": evidence,
                    "sources": sorted({item["source"] for item in evidence}),
                    "warnings": warnings,
                    "severity": "UNVERIFIED"
                    if score is None
                    else "CRITICAL"
                    if score >= 9
                    else "HIGH"
                    if score >= 7
                    else "BELOW_HIGH",
                    "fix_versions": vulnerability.fix_versions,
                    "assessment_status": "incomplete" if errors else "complete",
                    "errors": errors,
                    "blocked": bool(errors) or (score is not None and score >= THRESHOLD),
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
        "source": "NVD CVSS v3/v4 maximum; validated OSV CVSS v3/v4 fallback",
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
        with (
            httpx.Client(headers=headers, timeout=15, follow_redirects=False) as client,
            httpx.Client(
                timeout=15,
                follow_redirects=False,
                trust_env=False,
                headers={"Accept-Encoding": "identity"},
            ) as osv_client,
        ):
            report["findings"] = assess(dependencies, client, 0.6 if api_key else 6.0, osv_client)
        blocked = any(finding["blocked"] for finding in report["findings"])
        incomplete_count = sum(
            finding["assessment_status"] == "incomplete" for finding in report["findings"]
        )
        high_count = sum(
            any(item["cvss"] >= THRESHOLD for item in finding["score_evidence"])
            for finding in report["findings"]
        )
        report["status"] = "incomplete" if incomplete_count else "blocked" if blocked else "passed"
        report["summary"] = {
            "vulnerabilities_found": len(report["findings"]),
            "high_critical_findings": high_count,
            "incomplete_assessments": incomplete_count,
        }
        for finding in report["findings"]:
            # Escape control characters from external identifiers before printing.
            print(json.dumps(finding, ensure_ascii=True))
        print(f"Dependency audit {report['status']}; {len(dependencies)} packages scanned.")
        print("Dependency audit summary:")
        print(f"- Vulnerabilities found: {len(report['findings'])}")
        print(f"- Verified HIGH/CRITICAL findings: {high_count}")
        print(f"- Findings with incomplete assessment: {incomplete_count}")
        suffix = " - development checks blocked." if blocked else "."
        print(f"Result: {report['status'].upper()}{suffix}")
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 2 if incomplete_count else 1 if blocked else 0
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
