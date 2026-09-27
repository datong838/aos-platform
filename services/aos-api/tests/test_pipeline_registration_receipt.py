"""First-pipeline registration is a single receipt-bound metadata transaction."""

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest
from starlette.requests import Request

from aos_api import data_os_store
from aos_api.routers import wave_ext
from aos_api.tenant_scope import TenantScope


REVISION = "12345678-1234-1234-1234-123456789012"


def _principal():
    return SimpleNamespace(org_id="org-org", project_id="dev-project")


def _body():
    return wave_ext.PipelineRegistrationIn(pipelineId="P01-shop-qyh",sourceId="source-one",
        sourceConfigurationRevision=REVISION,name="栖月汇店铺")


def _request(*headers):
    return Request({"type":"http","method":"POST","path":"/v1/pipeline-registrations",
                    "headers":list(headers),"query_string":b""})


def test_product_entry_passes_original_key_and_refreshes_only_after_commit(monkeypatch):
    calls=[]
    def register(scope,**kwargs):
        calls.append(("commit",scope.key,kwargs.copy()))
        return {"id":kwargs["pipeline_id"],"datasetRid":kwargs["dataset_rid"]}
    monkeypatch.setattr(data_os_store,"register_pipeline",register)
    monkeypatch.setattr(wave_ext,"_hydrate_data_os_scope",
        lambda scope,**kwargs:calls.append(("refresh",scope.key,kwargs)))
    result=wave_ext.create_pipeline_registration(_body(),
        _request((b"idempotency-key",b"original-key")),_principal())
    assert result=={"id":"P01-shop-qyh","datasetRid":"ri.dataset.P01-shop-qyh"}
    assert [event[0] for event in calls]==["commit","refresh"]
    assert calls[0][2]["idempotency_key"]=="original-key"


def test_product_entry_rejects_bad_key_before_store(monkeypatch):
    monkeypatch.setattr(data_os_store,"register_pipeline",lambda *args,**kw:pytest.fail("must not write"))
    with pytest.raises(wave_ext.ApiError) as error:
        wave_ext.create_pipeline_registration(_body(),
            _request((b"idempotency-key",b"one"),(b"idempotency-key",b"two")),_principal())
    assert error.value.code=="PIPELINE_REGISTRATION_KEY_INVALID"


def test_unknown_store_result_keeps_original_key_for_readback(monkeypatch):
    monkeypatch.setattr(data_os_store,"register_pipeline",
        lambda *args,**kw:(_ for _ in ()).throw(RuntimeError("private-sentinel")))
    with pytest.raises(wave_ext.ApiError) as error:
        wave_ext.create_pipeline_registration(_body(),
            _request((b"idempotency-key",b"original-key")),_principal())
    assert error.value.code=="PIPELINE_REGISTRATION_UNCONFIRMED"
    assert "private-sentinel" not in str(error.value)


def test_receipt_readback_is_tenant_scoped_and_distinguishes_absence(monkeypatch):
    calls=[]
    def load(scope,pipeline_id,key):
        calls.append((scope.key,pipeline_id,key))
        return {"id":pipeline_id,"datasetRid":"ri.dataset."+pipeline_id}
    monkeypatch.setattr(data_os_store,"load_pipeline_registration_receipt",load)
    result=wave_ext.get_pipeline_registration_receipt("P01-shop-qyh","original-key",_principal())
    assert result["id"]=="P01-shop-qyh"
    assert calls==[(('org-org','dev-project'),'P01-shop-qyh','original-key')]
    monkeypatch.setattr(data_os_store,"load_pipeline_registration_receipt",lambda *args:None)
    with pytest.raises(wave_ext.ApiError) as error:
        wave_ext.get_pipeline_registration_receipt("P01-shop-qyh","original-key",_principal())
    assert error.value.code=="PIPELINE_REGISTRATION_RECEIPT_NOT_FOUND"


def test_store_same_key_replays_without_second_metadata_write(monkeypatch):
    state={"receipt":None,"pipeline":None,"dataset":None,"commits":0}
    class Cursor:
        def __init__(self,row=None): self.row=row
        def fetchone(self): return self.row
    class Connection:
        def execute(self,sql,params=None):
            if "SELECT request_hash,response_metadata FROM pipeline_registration_receipt" in sql:
                return Cursor(state["receipt"])
            if "SELECT configuration_revision FROM meta_source" in sql:
                return Cursor({"configuration_revision":UUID(REVISION)})
            if "SELECT 1 FROM meta_pipeline" in sql:return Cursor(state["pipeline"])
            if "SELECT 1 FROM meta_dataset" in sql:return Cursor(state["dataset"])
            if "INSERT INTO meta_pipeline" in sql:
                state["pipeline"]={"id":params[0]};return Cursor()
            if "INSERT INTO meta_dataset" in sql:
                state["dataset"]={"rid":params[0]};return Cursor()
            if "INSERT INTO pipeline_registration_receipt" in sql:
                import json
                state["receipt"]={"request_hash":params[3],"response_metadata":json.loads(params[8])}
                return Cursor()
            assert "pg_advisory_xact_lock" in sql
            return Cursor()
        def commit(self):state["commits"]+=1
    @contextmanager
    def connection(scope):
        assert scope.key==("org-org","dev-project")
        yield Connection()
    monkeypatch.setattr(data_os_store,"connect",connection)
    monkeypatch.setattr(data_os_store,"ensure_data_os_schema",lambda:None)
    args=dict(pipeline_id="P01-shop-qyh",source_id="source-one",
        source_configuration_revision=REVISION,dataset_rid="ri.dataset.P01-shop-qyh",
        name="栖月汇店铺",idempotency_key="original-key")
    scope=TenantScope("org-org","dev-project")
    first=data_os_store.register_pipeline(scope,**args)
    assert data_os_store.register_pipeline(scope,**args)==first
    assert state["commits"]==1
    with pytest.raises(data_os_store.ApiError) as error:
        data_os_store.register_pipeline(scope,**{**args,"name":"different"})
    assert error.value.code=="PIPELINE_REGISTRATION_KEY_CONFLICT"
