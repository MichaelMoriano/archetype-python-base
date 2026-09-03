"""X-Request-Id propagation using an async-safe ContextVar."""

import re
from contextvars import ContextVar
from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from python_ai_service.api.common.constants import REQUEST_ID_HEADER

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_current_request_id() -> str:
    value = _request_id_var.get()
    return value if value is not None else ""


def add_request_id_middleware(application: FastAPI) -> None:
    @application.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _REQUEST_ID_PATTERN.fullmatch(incoming) else str(uuid4())
        token = _request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            _request_id_var.reset(token)
