"""Safe HTTP access logging without request/response bodies or credentials."""

from time import perf_counter

import structlog
from fastapi import FastAPI, Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

logger = structlog.get_logger("http.access")


def add_access_log_middleware(application: FastAPI) -> None:
    @application.middleware("http")
    async def access_log_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        started = perf_counter()
        response = await call_next(request)
        duration_ms = round((perf_counter() - started) * 1000, 2)
        # request_id is injected by the structlog processor chain.
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response
