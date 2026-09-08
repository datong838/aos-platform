"""Bind a read observation to configuration inputs, without claiming connection identity."""
from typing import Literal, Self
from uuid import UUID

from pydantic import ConfigDict, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.source_read_observation import SourceReadObservation


class _FrozenConfigurationRef(InvestigationExactRef):
    model_config = ConfigDict(frozen=True)


class ConfiguredSourceObservation(AipContractModel):
    model_config = ConfigDict(frozen=True)
    schema_version: Literal["aos.configured-source-observation/v1"] = "aos.configured-source-observation/v1"
    observation: SourceReadObservation
    source_configuration_ref: _FrozenConfigurationRef
    configuration_identity_only: Literal[True] = True
    secret_material_version_known: Literal[False] = False
    connection_identity_verified: Literal[False] = False

    @model_validator(mode="after")
    def _configuration(self) -> Self:
        ref = self.source_configuration_ref
        if (ref.resource_type != "DataSourceConfigurationRevision" or type(ref.revision) is not int
            or ref.revision != 1 or ref.receipt_id is not None):
            raise ValueError("exact configuration reference required")
        revision = UUID(ref.resource_id.removeprefix("source-config-"))
        if ref.resource_id != "source-config-" + str(revision):
            raise ValueError("canonical configuration reference required")
        return self

    def verify_rows(self, rows) -> None:
        item = type(self).model_validate(self.model_dump())
        item.observation.verify_rows(rows)
