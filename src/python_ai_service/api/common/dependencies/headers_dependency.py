"""Validation of institutional request headers."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Header

from python_ai_service.api.common.constants import ORIGIN_ID_HEADER, SUB_ORIGIN_ID_HEADER


@dataclass(frozen=True, slots=True)
class InstitutionalHeaders:
    origin_id: int
    sub_origin_id: int


OriginIdHeader = Annotated[int, Header(alias=ORIGIN_ID_HEADER, gt=0)]
SubOriginIdHeader = Annotated[int, Header(alias=SUB_ORIGIN_ID_HEADER, gt=0)]


def get_institutional_headers(
    origin_id: OriginIdHeader,
    sub_origin_id: SubOriginIdHeader,
) -> InstitutionalHeaders:
    return InstitutionalHeaders(origin_id=origin_id, sub_origin_id=sub_origin_id)
