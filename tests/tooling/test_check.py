"""The pipeline must stop at any failed control, including incomplete audits."""

import subprocess
from typing import Any

import pytest
from scripts import check


@pytest.mark.parametrize("failed_step", range(7))
def test_every_failed_gate_prevents_later_steps(
    monkeypatch: pytest.MonkeyPatch, failed_step: int
) -> None:
    calls = _mock_steps(monkeypatch, failed_step)
    assert check.main([]) == 1
    assert len(calls) == failed_step + 1


def test_all_gates_pass_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _mock_steps(monkeypatch, -1)
    assert check.main([]) == 0
    assert [command[1] for command in calls[:5]] == ["lock", "run", "run", "run", "run"]
    assert calls[5][-1].endswith("audit_dependencies.py")
    assert "pysonar" in calls[6]


def test_missing_sonar_credentials_is_not_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _mock_steps(monkeypatch, -1)
    monkeypatch.delenv("SONAR_TOKEN")
    assert check.main([]) == 2
    assert len(calls) == 6


def test_missing_executable_is_not_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("private details")

    monkeypatch.setattr(subprocess, "run", fail)
    assert check.main([]) == 2


def _mock_steps(monkeypatch: pytest.MonkeyPatch, failed_step: int) -> list[list[str]]:
    calls: list[list[str]] = []
    monkeypatch.setenv("SONAR_TOKEN", "fake-token")
    monkeypatch.setenv("SONAR_HOST_URL", "http://sonar.invalid")
    monkeypatch.setenv("NVD_API_KEY", "fake-key")

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        index = len(calls)
        calls.append(command)
        assert kwargs["cwd"] == check.ROOT
        assert ("SONAR_TOKEN" in kwargs["env"]) == (index == 6)
        assert ("NVD_API_KEY" in kwargs["env"]) == (index == 5)
        return subprocess.CompletedProcess(command, 2 if index == failed_step else 0)

    monkeypatch.setattr(subprocess, "run", run)
    return calls
