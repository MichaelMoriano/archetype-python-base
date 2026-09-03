"""Shared API envelopes. Business schemas stay version-specific."""

from pydantic import BaseModel, ConfigDict


class ErrorMeta(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    meta: ErrorMeta
