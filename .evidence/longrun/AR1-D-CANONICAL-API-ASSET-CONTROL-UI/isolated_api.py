from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI

from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.extension_runtime.runtime_view import RuntimeBindingView, RuntimeInstallationView, RuntimeUiSessionView
from aos_api.routers import bundle_runtime_installations

INSTALLATION_ID = "11111111-1111-4111-8111-111111111111"
GENERATION = "22222222-2222-4222-8222-222222222222"


class IsolatedViewReader:
    def get_installation(self, **_kwargs):
        resource_hash = os.environ["AR1D_RESOURCE_HASH"]
        return RuntimeInstallationView(
            installationId=INSTALLATION_ID, installationRevision=5, installationEtag=5,
            installationState="active", effectiveState="ready",
            binding=RuntimeBindingView(
                generation=GENERATION, installationRevision=5, profileRef="internal-python-v1",
                configRef={"configurationId": "33333333-3333-4333-8333-333333333333"},
                executionEpoch=3, desiredState="enabled", observedState="ready",
                enabled=True, operationFence=False, revision=4,
            ),
            currentOperation=None,
            ui=RuntimeUiSessionView(
                title="隔离测试扩展",
                signedResourceUrl=f"http://127.0.0.1:18182/index.html?contentHash={resource_hash}",
                resourceHash=resource_hash, initialRoute="/workshop", routeClaims=("/workshop/*",),
                readOperationClaims=("read.orders",), commandOperationClaims=("command.content.create",),
            ),
            allowedActions=("disable",), reasons=(),
        )


def principal():
    return Principal(subject="isolated-browser", org_id="org-org", project_id="dev-project", roles=["admin"], markings=["public"])


app = FastAPI()
app.include_router(bundle_runtime_installations.router)
app.dependency_overrides[require_principal] = principal
app.state.extension_runtime_view_reader = IsolatedViewReader()
register_exception_handlers(app)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=18184, log_level="warning")
