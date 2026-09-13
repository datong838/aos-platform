"""Fixed UI read transport contracts. A queue receipt is not execution authority."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from aos_api.extension_runtime.ui_invocation import RuntimeUiInvocationTarget


class UiReadRequest(BaseModel):
    model_config=ConfigDict(strict=True,extra='forbid',frozen=True,hide_input_in_errors=True)
    schemaVersion: Literal['aos.runtime-ui-read-request/v1']
    operationId: Literal['analyst_workspace_view_v1']
    moduleId: Literal['ecommerce.analyst']
    target: RuntimeUiInvocationTarget
    caseLimit: int=Field(default=20,ge=1,le=50)
    runLimit: int=Field(default=5,ge=1,le=10)
