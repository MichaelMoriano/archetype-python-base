"""Minimal protected endpoint for checking remote Basic authentication."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from python_ai_service.api.common.dependencies.headers_dependency import (
    InstitutionalHeaders,
    get_institutional_headers,
)
from python_ai_service.api.common.dependencies.security_dependency import require_valid_basic_auth

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


@router.get("/basic/health", dependencies=[Depends(require_valid_basic_auth)])
async def health_basic_auth(
    headers: Annotated[InstitutionalHeaders, Depends(get_institutional_headers)],
) -> dict[str, str]:
    logger.info(
        "Health check for basic auth endpoint called with "
        "origin=%s, sub_origin=%s, correlation_id=%s",
        headers.origin_id,
        headers.sub_origin_id,
        headers.request_id,
    )
    return {
        "status": "ok",
        "origin": f"{headers.origin_id}",
        "sub_origin": f"{headers.sub_origin_id}",
        "correlation_id": f"{headers.request_id}",
    }
