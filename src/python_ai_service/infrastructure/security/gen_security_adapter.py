"""HTTP adapter for the currently deployed GEN-SECURITY token validation contract."""

import httpx

from python_ai_service.application.ports.security_validation_port import SecurityValidationPort
from python_ai_service.config.settings import Settings
from python_ai_service.domain.exceptions import (
    AuthenticationException,
    ExternalServiceException,
    ExternalServiceTimeoutException,
)
from python_ai_service.infrastructure.security.constants import (
    BEARER_SCHEME,
    CONTENT_TYPE_HEADER,
    CONTENT_TYPE_TEXT,
    GEN_SECURITY_ORIGIN_ID_HEADER,
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
        token: str,
    ) -> None:
        headers = {
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
