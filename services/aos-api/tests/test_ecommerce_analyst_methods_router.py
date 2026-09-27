"""Method product route: scoped, immutable, and fail-closed contract."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import (
    AnalystAuthorityConflict, AnalystAuthorityNotFound, canonical_hash,
)
from aos_api.routers.ecommerce_analyst_methods import get_method_store, router


class MethodStore:
    def __init__(self):
        self.items = {}
        self.receipts = {}
        self.calls = 0

    def publish_method(self, scope, actor, key, item, *, expected_version):
        self.calls += 1
        assert scope.key == ("org-org", "dev-project")
        assert actor == "user:editor"
        assert item.created_by == actor
        assert item.tenant.org_id == scope.org_id
        assert canonical_hash(item.model_dump(mode="json", by_alias=True, exclude={"content_hash"})) == item.content_hash
        request = (expected_version, item.model_dump(mode="json", by_alias=True))
        if key in self.receipts:
            previous, ref = self.receipts[key]
            if previous != request:
                raise AnalystAuthorityConflict("same key changed payload")
            return ref
        if expected_version != 0:
            raise AnalystAuthorityConflict("stale version")
        ref = AnalystExactRef(resourceType="MethodRevision", resourceId=item.method_id,
                              revision=item.revision, contentHash=item.content_hash)
        self.items[(scope.key, item.method_id)] = item
        self.receipts[key] = (request, ref)
        return ref

    def get_method_exact(self, scope, ref):
        item = self.items.get((scope.key, ref.resource_id))
        if item is None or item.content_hash != ref.content_hash or item.revision != ref.revision:
            raise AnalystAuthorityNotFound("not found")
        return item

    def get_method_current(self, scope, method_id):
        item = self.items.get((scope.key, method_id))
        if item is None:
            raise AnalystAuthorityNotFound("not found")
        return item

    def find_method_publication_receipt(self, scope, key):
        assert scope.key == ("org-org", "dev-project")
        receipt = self.receipts.get(key)
        return None if receipt is None else receipt[1]


def client(roles=("admin",)):
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    store = MethodStore()
    app.dependency_overrides[get_method_store] = lambda: store
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user:editor", org_id="org-org", project_id="dev-project", roles=list(roles)
    )
    return TestClient(app), store


BODY = {
    "methodId": "descriptive-snapshot", "name": "来源事实画像",
    "description": "归纳已披露事实并保留来源与限制",
    "algorithm": "descriptive_snapshot_v1", "insightKind": "observation",
    "minSourceItems": 1, "maxSourceAgeSeconds": 86400,
    "limitations": ["只描述观察，不证明因果"], "expectedVersion": 0,
    "createdAt": "2026-09-28T01:00:00+08:00",
}


def test_publish_replay_exact_current_and_receipt():
    http, store = client()
    path = "/v1/ecommerce/analyst/methods"
    first = http.post(path, json=BODY, headers={"Idempotency-Key": "method-1"})
    assert first.status_code == 201, first.text
    assert first.json()["method"]["createdBy"] == "user:editor"
    assert first.json()["method"]["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert http.post(path, json=BODY, headers={"Idempotency-Key": "method-1"}).json() == first.json()
    ref = first.json()["exactRef"]
    assert http.get(f"{path}/receipts/method-1").json() == ref
    assert http.get(f"{path}/descriptive-snapshot/current").json() == first.json()["method"]
    assert http.get(f"{path}/descriptive-snapshot/revisions/1/{ref['contentHash']}").json() == first.json()["method"]
    assert store.calls == 2


def test_write_fails_closed_on_role_key_payload_and_unknown_ref():
    path = "/v1/ecommerce/analyst/methods"
    readonly, store = client(("viewer",))
    assert readonly.post(path, json=BODY, headers={"Idempotency-Key": "k"}).status_code == 403
    assert store.calls == 0
    http, store = client()
    assert http.post(path, json=BODY).status_code == 400
    assert http.post(path, json={**BODY, "tenant": {"orgId": "dev-org"}}, headers={"Idempotency-Key": "k"}).status_code == 400
    assert http.post(path, json={**BODY, "insightKind": "causal_claim"}, headers={"Idempotency-Key": "k"}).status_code == 400
    assert http.get(f"{path}/missing/current").status_code == 404
    assert http.get(f"{path}/receipts/missing").json() is None
    assert store.calls == 0


def test_same_key_changed_payload_conflicts():
    http, store = client()
    path = "/v1/ecommerce/analyst/methods"
    assert http.post(path, json=BODY, headers={"Idempotency-Key": "k"}).status_code == 201
    changed = {**BODY, "description": "另一个描述"}
    assert http.post(path, json=changed, headers={"Idempotency-Key": "k"}).status_code == 409
    assert store.calls == 2
