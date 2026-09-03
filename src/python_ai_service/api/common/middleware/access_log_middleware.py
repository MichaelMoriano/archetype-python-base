"""Safe HTTP access logging without request/response bodies or credentials."""

import logging
from time import perf_counter

from fastapi import FastAPI, Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from python_ai_service.api.common.middleware.request_id_middleware import get_current_request_id

logger = logging.getLogger("http.access")


def add_access_log_middleware(application: FastAPI) -> None:
    @application.middleware("http")
    async def access_log_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        started = perf_counter()
        response = await call_next(request)
        duration_ms = round((perf_counter() - started) * 1000, 2)
        logger.info(
            "request_completed method=%s path=%s status=%s duration_ms=%s request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            get_current_request_id(),
        )
        return response
