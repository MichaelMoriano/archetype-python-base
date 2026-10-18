"""Validation of institutional request headers."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Header

from python_ai_service.api.common.constants import (
    ORIGIN_ID_HEADER,
    REQUEST_ID_HEADER,
    SUB_ORIGIN_ID_HEADER,
)
from python_ai_service.api.common.middleware.request_id_middleware import get_current_request_id


@dataclass(frozen=True, slots=True)
class InstitutionalHeaders:
    origin_id: int
    sub_origin_id: int
    request_id: str


OriginIdHeader = Annotated[int, Header(alias=ORIGIN_ID_HEADER, gt=0)]
SubOriginIdHeader = Annotated[int, Header(alias=SUB_ORIGIN_ID_HEADER, gt=0)]
RequestIdHeader = Annotated[str, Header(alias=REQUEST_ID_HEADER, min_length=1)]


def get_institutional_headers(
    origin_id: OriginIdHeader, sub_origin_id: SubOriginIdHeader
) -> InstitutionalHeaders:
    return InstitutionalHeaders(
        origin_id=origin_id, sub_origin_id=sub_origin_id, request_id=get_current_request_id()
    )
