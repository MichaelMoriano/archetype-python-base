import json
from typing import Any

from python_ai_service.application.ports.logging_port import LoggingPort
from python_ai_service.config.logging import configure_logging
from python_ai_service.config.request_id_context import bind_request_id, reset_request_id
from python_ai_service.infrastructure.logging.structlog_logger_adapter import StructlogLoggerAdapter


def _last_json_line(captured: str) -> dict[str, Any]:
    lines = [line for line in captured.strip().splitlines() if line.strip()]
    assert lines, "no log output was captured"
    parsed: dict[str, Any] = json.loads(lines[-1])
    return parsed


def test_adapter_satisfies_logging_port() -> None:
    # The annotation is the static check; the assertions below guard it at runtime.
    adapter: LoggingPort = StructlogLoggerAdapter(name="test")
    for method in ("bind", "debug", "info", "warning", "error", "exception"):
        assert callable(getattr(adapter, method))


def test_emitted_line_is_valid_json_with_structured_context(
    capsys: Any,
) -> None:
    configure_logging("INFO")
    adapter = StructlogLoggerAdapter(name="test.logger")
    adapter.info("user_created", user_id=42, tenant="acme")

    payload = _last_json_line(capsys.readouterr().err)
    assert payload["event"] == "user_created"
    assert payload["user_id"] == 42
    assert payload["tenant"] == "acme"
    assert payload["level"] == "info"
    assert payload["logger"] == "test.logger"
    assert payload["timestamp"].endswith("Z")


def test_bind_forwards_context_to_every_event(capsys: Any) -> None:
    configure_logging("INFO")
    adapter = StructlogLoggerAdapter(name="test.logger")
    bound = adapter.bind(component="billing")
    bound.info("invoice_issued", amount=10)

    payload = _last_json_line(capsys.readouterr().err)
    assert payload["component"] == "billing"
    assert payload["amount"] == 10


def test_request_id_is_injected_inside_a_request_context(capsys: Any) -> None:
    configure_logging("INFO")
    adapter = StructlogLoggerAdapter(name="test.logger")
    token = bind_request_id("req-abc-123")
    try:
        adapter.info("inside_request")
    finally:
        reset_request_id(token)

    payload = _last_json_line(capsys.readouterr().err)
    assert payload["request_id"] == "req-abc-123"


def test_request_id_is_absent_outside_a_request_context(capsys: Any) -> None:
    configure_logging("INFO")
    adapter = StructlogLoggerAdapter(name="test.logger")
    adapter.info("outside_request")

    payload = _last_json_line(capsys.readouterr().err)
    assert "request_id" not in payload
