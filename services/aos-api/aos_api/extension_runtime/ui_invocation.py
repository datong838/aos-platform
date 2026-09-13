"""UI invocation preconditions, never a persistent execution authority."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from aos_api.extension_runtime.ui_resources import _canonical_route

_UUID = r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'


class RuntimeUiInvocationTarget(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True, hide_input_in_errors=True)
    installationId: str = Field(pattern=_UUID)
    installationRevision: int = Field(ge=1)
    generation: str = Field(pattern=_UUID)
    executionEpoch: int = Field(ge=1)
    bindingRevision: int = Field(ge=1)
    route: str = Field(min_length=1, max_length=512)
    resourceHash: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')

    @field_validator('route')
    @classmethod
    def canonical_route(cls, value):
        if not _canonical_route(value):
            raise ValueError('exact UI route required')
        return value


def require_current_ui_invocation(*, current, target: RuntimeUiInvocationTarget,
                                  kind: Literal['read', 'command'], operation_id: str) -> None:
    """Check freshly loaded server facts; caller must still enter governed execution."""
    if type(target) is not RuntimeUiInvocationTarget:
        raise TypeError('exact UI target required')
    if kind not in ('read', 'command') or type(operation_id) is not str or not operation_id:
        raise PermissionError('UI operation is not declared')
    binding, ui = current.binding, current.ui
    if (current.effectiveState != 'ready' or current.installationId != target.installationId
            or current.installationRevision != target.installationRevision or binding is None or ui is None):
        raise PermissionError('UI runtime is no longer current')
    if (binding.generation != target.generation or binding.executionEpoch != target.executionEpoch
            or binding.revision != target.bindingRevision or binding.installationRevision != target.installationRevision
            or binding.enabled is not True or binding.operationFence is not False
            or ui.resourceHash != target.resourceHash or ui.initialRoute != target.route
            or target.route not in ui.routeClaims):
        raise PermissionError('UI runtime is no longer current')
    claims = ui.readOperationClaims if kind == 'read' else ui.commandOperationClaims
    if operation_id not in claims:
        raise PermissionError('UI operation is not declared')
