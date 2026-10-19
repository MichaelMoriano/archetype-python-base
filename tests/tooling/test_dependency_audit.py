"""Exercise the audit command without public queries or real vulnerable packages."""

import json
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from scripts import audit_dependencies as audit


@pytest.fixture(autouse=True)
def isolate_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NVD_API_KEY", raising=False)


def test_audit_help() -> None:
    with pytest.raises(SystemExit) as result:
        audit.main(["--help"])
    assert result.value.code == 0


@pytest.mark.parametrize(
    ("scores", "expected"),
    [([], 0), ([6.9], 0), ([7.0], 1), ([8.9], 1), ([9.0], 1), ([10.0], 1)],
)
def test_audit_enforces_cvss_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scores: list[float], expected: int
) -> None:
    report = _run(tmp_path, monkeypatch, scores=scores)
    assert report[0] == expected
    assert report[1]["status"] == ("blocked" if expected else "passed")


@pytest.mark.parametrize(
    "failure",
    [
        "export",
        "command_timeout",
        "command_missing",
        "scanner",
        "invalid_json",
        "skipped",
        "empty_inventory",
        "missing_package",
        "unresolved",
        "unpinned",
        "url_dependency",
        "empty_nvd",
        "unsupported_cvss",
        "missing_alias",
        "missing_score",
        "invalid_score",
        "boolean_score",
        "secret_score",
        "ssvc_only",
        "wrong_cve",
        "rejected_cve",
        "timeout",
        "http_error",
        "nvd_schema",
        "contradictory_exit",
    ],
)
def test_incomplete_audits_never_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, report = _run(tmp_path, monkeypatch, scores=[8.0], failure=failure)
    assert code == 2
    assert report["status"] == "incomplete"
    assert "private-secret" not in capsys.readouterr().out
    assert "private-secret" not in json.dumps(report)


def test_highest_score_wins_and_key_is_not_in_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NVD_API_KEY", "private-secret")
    code, report = _run(tmp_path, monkeypatch, scores=[4.0, 9.1])
    assert code == 1
    assert report["findings"][0]["cvss"] == 9.1
    assert "private-secret" not in json.dumps(report)


def test_cvss_v4_maximum_across_aliases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    code, report = _run(
        tmp_path,
        monkeypatch,
        scores=[6.9, 9.0],
        failure="cvss_v4",
        aliases=["CVE-2026-12345", "CVE-2026-54321"],
    )
    assert code == 1
    assert report["findings"][0]["cvss_by_cve"] == {
        "CVE-2026-12345": 6.9,
        "CVE-2026-54321": 9.0,
    }
    assert report["findings"][0]["cvss"] == 9.0


def test_nvd_ssvc_metadata_does_not_hide_high_cvss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    code, report = _run(tmp_path, monkeypatch, scores=[8.1], failure="ssvc_metrics")
    assert code == 1
    assert report["status"] == "blocked"
    assert report["findings"][0]["cvss"] == 8.1
    assert report["findings"][0]["severity"] == "HIGH"


@pytest.mark.parametrize(
    ("failure", "category", "http_status"),
    [
        ("http_error", "http_status", 403),
        ("http429", "http_status", 429),
        ("http503", "http_status", 503),
        ("timeout", "timeout", None),
        ("connection", "network", None),
        ("proxy", "network", None),
        ("invalid_nvd_json", "invalid_json", 200),
        ("nvd_schema", "schema", 200),
        ("invalid_score", "schema", 200),
        ("secret_score", "schema", 200),
        ("ssvc_only", "missing_score", 200),
        ("missing_score", "missing_score", 200),
        ("empty_nvd", "record_missing", 200),
        ("wrong_cve", "record_mismatch", 200),
    ],
)
def test_nvd_failure_has_safe_actionable_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
    category: str,
    http_status: int | None,
) -> None:
    monkeypatch.setenv("NVD_API_KEY", "private-secret")
    code, report = _run(tmp_path, monkeypatch, scores=[8.0], failure=failure)
    assert code == 2
    assert report["status"] == "incomplete"
    assert report["error_context"]["category"] == category
    assert report["error_context"]["cve_id"] == "CVE-2026-12345"
    assert report["error_context"].get("http_status") == http_status
    output = capsys.readouterr().out
    assert "CVE-2026-12345" in output
    if http_status is not None:
        assert f"HTTP {http_status}" in output
    if failure == "invalid_score":
        assert "baseScore" in report["error_context"]["field"]
    assert "private-secret" not in output
    assert "private-secret" not in json.dumps(report)


def _run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    scores: list[float],
    failure: str = "",
    aliases: list[str] | None = None,
) -> tuple[int, dict[str, Any]]:
    cve_ids = aliases or ["CVE-2026-12345"]
    finding = {
        "id": "PYSEC-2026-1",
        "aliases": [] if failure == "missing_alias" else cve_ids,
        "fix_versions": ["2.0"],
    }
    dependencies: list[dict[str, Any]] = [
        {"name": "example-package", "version": "1.0", "vulns": [finding] if scores else []}
    ]
    if failure == "skipped":
        dependencies = [{"name": "example-package", "skip_reason": "private-secret"}]
    if failure == "empty_inventory":
        dependencies = []
    if failure == "missing_package":
        dependencies[0]["name"] = "different-package"
    if failure == "unresolved":
        dependencies[0].pop("version")

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert kwargs["cwd"] == audit.ROOT
        assert "NVD_API_KEY" not in kwargs["env"]
        assert "SONAR_TOKEN" not in kwargs["env"]
        assert "--fix" not in command
        if failure == "command_timeout":
            raise subprocess.TimeoutExpired(command, 300, stderr="private-secret")
        if failure == "command_missing":
            raise FileNotFoundError("private-secret")
        if command[0] == "uv":
            assert "--locked" in command and "--no-emit-project" in command
            path = Path(command[command.index("--output-file") + 1])
            requirement = {
                "empty_inventory": "",
                "unpinned": "example-package>=1.0\n",
                "url_dependency": "example-package @ https://example.invalid/package.whl\n",
            }.get(failure, "example-package==1.0\n")
            path.write_text(requirement)
            return subprocess.CompletedProcess(
                command, int(failure == "export"), "", "private-secret"
            )
        assert "--disable-pip" in command and "--no-deps" in command and "--strict" in command
        path = Path(command[command.index("--output") + 1])
        path.write_text(
            "{" if failure == "invalid_json" else json.dumps({"dependencies": dependencies}),
            encoding="utf-8",
        )
        code = 3 if failure == "scanner" else int(bool(scores))
        if failure == "contradictory_exit":
            code = 0
        return subprocess.CompletedProcess(command, code, "", "private-secret")

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "services.nvd.nist.gov"
        identifier = request.url.params["cveId"]
        assert identifier in cve_ids
        if failure == "timeout":
            raise httpx.ReadTimeout("private-secret", request=request)
        if failure == "connection":
            raise httpx.ConnectError("private-secret", request=request)
        if failure == "proxy":
            raise httpx.ProxyError("private-secret", request=request)
        if failure == "http_error":
            return httpx.Response(403, text="private-secret")
        if failure in {"http429", "http503"}:
            return httpx.Response(int(failure.removeprefix("http")), text="private-secret")
        if failure == "invalid_nvd_json":
            return httpx.Response(200, text="<html>private-secret</html>")
        if failure == "nvd_schema":
            return httpx.Response(200, json={})
        if failure == "empty_nvd":
            return httpx.Response(200, json={"totalResults": 0, "vulnerabilities": []})
        values = [scores[cve_ids.index(identifier)]] if len(cve_ids) > 1 else scores
        cve: dict[str, Any] = {
            "id": "CVE-2026-99999" if failure == "wrong_cve" else identifier,
            "vulnStatus": "Rejected" if failure == "rejected_cve" else "Analyzed",
            "metrics": {
                "cvssMetricV31": [
                    {
                        "cvssData": {
                            "baseScore": (
                                "private-secret"
                                if failure == "secret_score"
                                else True
                                if failure == "boolean_score"
                                else 11.0
                                if failure == "invalid_score"
                                else value
                            )
                        }
                    }
                    for value in values
                ]
                if failure != "missing_score"
                else []
            },
        }
        if failure == "unsupported_cvss":
            cve["metrics"] = {"cvssMetricV2": [{"cvssData": {"baseScore": 6.0}}]}
        if failure == "cvss_v4":
            cve["metrics"] = {"cvssMetricV40": cve["metrics"]["cvssMetricV31"]}
        if failure in {"ssvc_metrics", "ssvc_only"}:
            cve["metrics"]["ssvcV203"] = [
                {"source": "CISA", "ssvcData": {"version": "2.0.3", "role": "CISA Coordinator"}}
            ]
            if failure == "ssvc_only":
                del cve["metrics"]["cvssMetricV31"]
        return httpx.Response(200, json={"totalResults": 1, "vulnerabilities": [{"cve": cve}]})

    real_client = httpx.Client
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    output = tmp_path / "reports"
    output.mkdir()
    # A failed new run must not leave a previous PASS visible.
    (output / "dependency-audit.json").write_text('{"status":"passed"}')
    code = audit.main(["--report-dir", str(output)])
    return code, json.loads((output / "dependency-audit.json").read_text(encoding="utf-8"))
