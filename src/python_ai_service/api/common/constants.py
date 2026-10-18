"""Stable HTTP contract constants shared by API adapters."""

from typing import Final

API_ROOT: Final = "/api"
API_V1_PREFIX: Final = f"{API_ROOT}/v1"
ORIGIN_ID_HEADER: Final = "OriginId"
SUB_ORIGIN_ID_HEADER: Final = "SubOriginId"
REQUEST_ID_HEADER: Final = "X-Request-Id"
SERVICE_NAME: Final = "ServiceName"
