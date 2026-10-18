import httpx
import pytest

from python_ai_service.domain.exceptions import AuthenticationException, ExternalServiceException
from python_ai_service.infrastructure.security.gen_security_adapter import GenSecurityAdapter
from tests.settings_helpers import SettingsWithoutDotenv, build_test_settings


def _settings() -> SettingsWithoutDotenv:
    return build_test_settings()


@pytest.mark.asyncio
async def test_valid_return_code_allows_request() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"returnCode": "000", "returnDescription": "OK"},
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = GenSecurityAdapter(client=client, settings=_settings())
        await adapter.validate_jwt(origin_id=26, sub_origin_id=105, request_id="test", token="abc")


@pytest.mark.asyncio
async def test_invalid_token_code_is_authentication_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            406,
            json={"returnCode": "044", "returnDescription": "INVALID"},
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = GenSecurityAdapter(client=client, settings=_settings())
        with pytest.raises(AuthenticationException):
            await adapter.validate_jwt(
                origin_id=26, sub_origin_id=105, request_id="test", token="abc"
            )


@pytest.mark.asyncio
async def test_unknown_contract_code_is_external_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            500,
            json={"returnCode": "999", "returnDescription": "x"},
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = GenSecurityAdapter(client=client, settings=_settings())
        with pytest.raises(ExternalServiceException):
            await adapter.validate_jwt(
                origin_id=26, sub_origin_id=105, request_id="test", token="abc"
            )
