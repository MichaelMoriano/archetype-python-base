"""GEN-SECURITY protocol constants."""

from typing import Final

BEARER_SCHEME: Final = "Bearer"
CONTENT_TYPE_HEADER: Final = "Content-Type"
CONTENT_TYPE_TEXT: Final = "text/plain"
GEN_SECURITY_ORIGIN_ID_HEADER: Final = "OriginId"
GEN_SECURITY_SUB_ORIGIN_ID_HEADER: Final = "SubOriginId"
GEN_SECURITY_REQUEST_ID_HEADER: Final = "X-Request-Id"
GEN_SECURITY_CONTENT_TYPE: Final = "application/json"
SUCCESS_RETURN_CODE: Final = "000"
INVALID_TOKEN_CODES: Final = frozenset({"042", "044"})
INTERNAL_ERROR_CODES: Final = frozenset({"003"})
