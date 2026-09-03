"""External GEN-SECURITY response models. Never leak these into application/domain."""

from pydantic import BaseModel, ConfigDict, Field


class GenSecurityResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    return_code: str = Field(alias="returnCode")
    return_description: str | None = Field(default=None, alias="returnDescription")
    data: object | None = None
