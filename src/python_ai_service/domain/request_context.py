"""Request metadata propagated to application use cases."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str
    origin_id: int
    sub_origin_id: int
