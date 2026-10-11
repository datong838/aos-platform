"""Narrow host ports and exact references visible to the Niushop adapter."""

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from aos_extension_sdk import ConnectorPort, ConnectorRequest, DispatchRef, request_connector


class AdapterContract(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class ExactRef(AdapterContract):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=240)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    receipt_id: str | None = Field(default=None, min_length=1, max_length=240)


__all__ = [
    "AdapterContract", "ConnectorPort", "ConnectorRequest", "DispatchRef", "ExactRef",
    "request_connector",
]
