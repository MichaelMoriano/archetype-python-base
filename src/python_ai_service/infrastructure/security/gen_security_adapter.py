"""HTTP adapter for the currently deployed GEN-SECURITY token validation contract."""

import base64
import binascii
import re
from typing import Literal

import httpx

from python_ai_service.application.ports.security_validation_port import SecurityValidationPort
from python_ai_service.config.settings import Settings
from python_ai_service.domain.exceptions import (
    AuthenticationException,
    ExternalServiceException,
    ExternalServiceTimeoutException,
    MalformedCredentialsException,
    MissingCredentialsException,
    UnsupportedAuthenticationSchemeException,
)
from python_ai_service.infrastructure.security.constants import (
    BEARER_SCHEME,
    CONTENT_TYPE_HEADER,
    CONTENT_TYPE_TEXT,
    GEN_SECURITY_CONTENT_TYPE,
    GEN_SECURITY_ORIGIN_ID_HEADER,
    GEN_SECURITY_REQUEST_ID_HEADER,
    GEN_SECURITY_SUB_ORIGIN_ID_HEADER,
    INTERNAL_ERROR_CODES,
    INVALID_TOKEN_CODES,
    SUCCESS_RETURN_CODE,
)
from python_ai_service.infrastructure.security.gen_security_dto import GenSecurityResponse


class GenSecurityAdapter(SecurityValidationPort):
    def __init__(self, *, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def validate_jwt(
        self,
        *,
        origin_id: int,
        sub_origin_id: int,
        request_id: str,
        token: str,
    ) -> None:

        _validate_header_authorization(f"{BEARER_SCHEME} {token}", expected_scheme="bearer")

        headers: dict[str, str] = {
            GEN_SECURITY_REQUEST_ID_HEADER: request_id,
            GEN_SECURITY_ORIGIN_ID_HEADER: str(origin_id),
            GEN_SECURITY_SUB_ORIGIN_ID_HEADER: str(sub_origin_id),
            CONTENT_TYPE_HEADER: CONTENT_TYPE_TEXT,
        }
        try:
            if self._settings.gen_security_use_basic_auth:
                assert self._settings.gen_security_username is not None
                assert self._settings.gen_security_password is not None
                response = await self._client.post(
                    self._settings.gen_security_validate_url,
                    headers=headers,
                    content=f"{BEARER_SCHEME} {token}",
                    auth=(
                        self._settings.gen_security_username,
                        self._settings.gen_security_password.get_secret_value(),
                    ),
                )
            else:
                response = await self._client.post(
                    self._settings.gen_security_validate_url,
                    headers=headers,
                    content=f"{BEARER_SCHEME} {token}",
                )
        except httpx.TimeoutException as error:
            raise ExternalServiceTimeoutException(
                "Security validation service timed out."
            ) from error
        except httpx.HTTPError as error:
            raise ExternalServiceException("Security validation service is unavailable.") from error

        _validate_security_response(response)

    async def validate_basic_auth(
        self,
        *,
        origin_id: int,
        sub_origin_id: int,
        request_id: str,
        encoded_basic_auth: str,
    ) -> None:
        _validate_header_authorization(encoded_basic_auth, expected_scheme="basic")

        headers = _build_request_headers(
            technical_auth=encoded_basic_auth,
            request_id=request_id,
            origin_id=origin_id,
            sub_origin_id=sub_origin_id,
        )

        try:
            response = await self._client.post(
                self._settings.gen_security_basic_auth_url, headers=headers, json={}
            )
        except httpx.TimeoutException as error:
            raise ExternalServiceTimeoutException(
                "Security validation service timed out."
            ) from error
        except httpx.HTTPError as error:
            raise ExternalServiceException("Security validation service is unavailable.") from error

        _validate_security_response(response)


def _validate_security_response(response: httpx.Response) -> None:
    try:
        envelope = GenSecurityResponse.model_validate(response.json())
    except (ValueError, TypeError) as error:
        raise ExternalServiceException(
            "Security validation service returned an invalid contract."
        ) from error

    if envelope.return_code == SUCCESS_RETURN_CODE:
        if not response.is_success:
            raise ExternalServiceException(
                "Security validation service returned an inconsistent response."
            )
        return

    if envelope.return_code in INVALID_TOKEN_CODES:
        raise AuthenticationException("Invalid authentication token.")

    if envelope.return_code in INTERNAL_ERROR_CODES:
        raise ExternalServiceException("Security validation service failed.")

    raise ExternalServiceException("Security validation service rejected the request.")


def _build_request_headers(
    *, technical_auth: str, request_id: str, origin_id: int, sub_origin_id: int
) -> dict[str, str]:
    headers: dict[str, str] = {
        CONTENT_TYPE_HEADER: GEN_SECURITY_CONTENT_TYPE,
        GEN_SECURITY_REQUEST_ID_HEADER: request_id,
        GEN_SECURITY_ORIGIN_ID_HEADER: str(origin_id),
        GEN_SECURITY_SUB_ORIGIN_ID_HEADER: str(sub_origin_id),
        "Authorization": technical_auth,
    }
    return headers


def _validate_header_authorization(
    authorization: str | None,
    *,
    expected_scheme: Literal["bearer", "basic"] | None = None,
) -> None:
    """Check credential syntax only; GEN-SECURITY owns authentication."""
    if authorization is None:
        raise MissingCredentialsException("Missing Authorization header")

    if not authorization.strip():
        raise MalformedCredentialsException("Empty Authorization header")

    scheme, separator, credentials = authorization.partition(" ")
    if not scheme or not separator:
        raise MalformedCredentialsException("Malformed Authorization header")

    scheme_lower = scheme.lower()
    if scheme_lower not in {"bearer", "basic"}:
        raise UnsupportedAuthenticationSchemeException("Unsupported authentication scheme")
    if expected_scheme is not None and scheme_lower != expected_scheme:
        raise UnsupportedAuthenticationSchemeException("Unexpected authentication scheme")

    credentials = credentials.lstrip(" ")
    if re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", credentials) is None:
        raise MalformedCredentialsException("Malformed authentication credentials")

    if scheme_lower == "basic":
        _validate_basic_credentials(credentials)


def _validate_basic_credentials(credentials: str) -> None:
    """Validate Basic encoding and structure without authenticating the caller."""
    try:
        decoded = base64.b64decode(credentials, validate=True)
    except binascii.Error as error:
        raise MalformedCredentialsException("Invalid Basic credentials encoding") from error
    if base64.b64encode(decoded).decode("ascii") != credentials:
        raise MalformedCredentialsException("Invalid Basic credentials encoding")
    if b":" not in decoded or any(byte < 32 or byte == 127 for byte in decoded):
        raise MalformedCredentialsException("Malformed Basic credentials")
