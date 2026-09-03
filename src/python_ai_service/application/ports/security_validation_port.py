"""Outbound security contract required by protected API routes."""

from typing import Protocol


class SecurityValidationPort(Protocol):
    async def validate_jwt(
        self,
        *,
        origin_id: int,
        sub_origin_id: int,
        token: str,
    ) -> None:
        """Validate the caller JWT or raise a controlled exception."""
        ...
