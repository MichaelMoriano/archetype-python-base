"""Build the framework-independent context after institutional authentication."""

from typing import Annotated

from fastapi import Depends

from python_ai_service.api.common.dependencies.headers_dependency import (
    InstitutionalHeaders,
    get_institutional_headers,
)
from python_ai_service.api.common.dependencies.security_dependency import require_valid_jwt
from python_ai_service.config.request_id_context import get_current_request_id
from python_ai_service.domain.request_context import RequestContext


def get_request_context(
    headers: Annotated[InstitutionalHeaders, Depends(get_institutional_headers)],
    _: Annotated[None, Depends(require_valid_jwt)],
) -> RequestContext:
    return RequestContext(
        request_id=get_current_request_id(),
        origin_id=headers.origin_id,
        sub_origin_id=headers.sub_origin_id,
    )
