import base64

import httpx
import pytest

from python_ai_service.domain.exceptions import (
    AuthenticationException,
    MalformedCredentialsException,
    MissingCredentialsException,
    UnsupportedAuthenticationSchemeException,
)
from python_ai_service.infrastructure.security.gen_security_adapter import (
    GenSecurityAdapter,
    _validate_header_authorization,
)
from tests.settings_helpers import build_test_settings


@pytest.mark.parametrize(
    "authorization",
    [
        "Bearer abc",
        "bEaReR abc.def.signature",
        "Bearer abc-._~+/==",
        "Bearer   abc",
        "Basic dXNlcjpwYXNz",
        "bAsIc   dXNlcjpwYXNz",
        "Basic " + base64.b64encode(b"user:pass:word").decode("ascii"),
        "Basic " + base64.b64encode("usuario:contrase\u00f1a".encode()).decode("ascii"),
        "Basic Og==",
    ],
)
def test_valid_authorization_syntax(authorization: str) -> None:
    _validate_header_authorization(authorization)


def test_missing_authorization() -> None:
    with pytest.raises(MissingCredentialsException):
        _validate_header_authorization(None)


@pytest.mark.parametrize(
    "authorization",
    [
        "",
        " ",
        "Bearer",
        "Basic",
        "Bearer ",
        "Basic   ",
        " Bearer abc",
        "Bearer\tabc",
        "Bearer abc def",
        "Bearer abc ",
        "Bearer abc\t",
        "Bearer abc\r\nX-Injected: value",
        "Bearer abc\x00",
        "Bearer t\u00f3ken",
        "Bearer abc,Basic dXNlcjpwYXNz",
        "Bearer ab=c",
        "Basic !!!",
        "Basic dXNlcjpwYXNz=",
        "Basic Oh==",
        "Basic dXNlcjpwYXN",
        "Basic dXNlcg==",
        "Basic ____",
        "Basic " + base64.b64encode(b"user:pass\n").decode("ascii"),
        "Basic " + base64.b64encode(b"us\x7fer:pass").decode("ascii"),
    ],
)
def test_malformed_authorization(authorization: str) -> None:
    with pytest.raises(MalformedCredentialsException):
        _validate_header_authorization(authorization)


@pytest.mark.parametrize("authorization", ["Digest abc", "JWT abc", "B\u00e1sic abc"])
def test_unsupported_scheme(authorization: str) -> None:
    with pytest.raises(UnsupportedAuthenticationSchemeException):
        _validate_header_authorization(authorization)


def test_unexpected_scheme() -> None:
    with pytest.raises(UnsupportedAuthenticationSchemeException):
        _validate_header_authorization("Bearer abc", expected_scheme="basic")
    with pytest.raises(UnsupportedAuthenticationSchemeException):
        _validate_header_authorization("Basic dXNlcjpwYXNz", expected_scheme="bearer")


@pytest.mark.asyncio
async def test_adapter_preserves_outbound_credentials() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"returnCode": "000", "returnDescription": "OK"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        adapter = GenSecurityAdapter(client=client, settings=build_test_settings())
        await adapter.validate_jwt(origin_id=26, sub_origin_id=105, request_id="test", token="abc")
        await adapter.validate_basic_auth(
            origin_id=26,
            sub_origin_id=105,
            request_id="test",
            encoded_basic_auth="Basic dXNlcjpwYXNz",
        )

    assert len(requests) == 2
    assert requests[0].content == b"Bearer abc"
    assert requests[1].headers["Authorization"] == "Basic dXNlcjpwYXNz"


@pytest.mark.asyncio
@pytest.mark.parametrize("credentials", ["Bearer abc", "Basic !!!", "Basic dXNlcg=="])
async def test_invalid_basic_never_calls_validator(credentials: str) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"returnCode": "000", "returnDescription": "OK"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        adapter = GenSecurityAdapter(client=client, settings=build_test_settings())
        with pytest.raises(AuthenticationException):
            await adapter.validate_basic_auth(
                origin_id=26,
                sub_origin_id=105,
                request_id="test",
                encoded_basic_auth=credentials,
            )

    assert requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("token", ["", "Bearer abc", "abc def", "abc\r\n"])
async def test_invalid_bearer_never_calls_validator(token: str) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"returnCode": "000", "returnDescription": "OK"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        adapter = GenSecurityAdapter(client=client, settings=build_test_settings())
        with pytest.raises(MalformedCredentialsException):
            await adapter.validate_jwt(
                origin_id=26, sub_origin_id=105, request_id="test", token=token
            )

    assert requests == []
