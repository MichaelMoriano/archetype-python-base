"""Outbound security contract required by protected API routes."""

from typing import Protocol


class SecurityValidationPort(Protocol):
    async def validate_jwt(
        self,
        *,
        origin_id: int,
        sub_origin_id: int,
        request_id: str,
        token: str,
    ) -> None:
        """Validate the raw caller token (without Bearer) or raise a controlled exception."""
        ...

    async def validate_basic_auth(
        self,
        *,
        origin_id: int,
        sub_origin_id: int,
        request_id: str,
        encoded_basic_auth: str,
    ) -> None:
        """Validate a complete Basic Authorization value or raise a controlled exception."""
        ...
