from datetime import datetime,timezone
import pytest
from psycopg import sql
from test_lifecycle_pg import database,seed,pytestmark


def envelope(installation):
    from aos_api.extension_runtime.audit_envelopes import AuditEnvelope,ExactRef
    ref=ExactRef(authority="result",id="example-result",revision=1,hash="sha256:"+"a"*64)
    return AuditEnvelope(installation_id=installation,business_title="商品分析结果",
        summary="已核对商品资料，建议补齐详情说明。",actor="test-actor",occurred_at=datetime.now(timezone.utc),
        source_ref=ref,schema_ref=ref,retention_policy_ref=ref)


def scoped(conn,role):
    conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
    conn.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")


def test_audit_no_runtime_needed_replay_conflict_and_revocation(database):
    from aos_api.extension_runtime.audit_envelopes import append_envelope,read_envelope
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    conn,role,_=database
    installation,_=seed(conn)
    item=envelope(installation)
    scoped(conn,role)
    with conn.transaction():
        first=append_envelope(conn,org_id="org-org",project_id="dev-project",envelope=item,authorize=lambda c,r:True)
        assert append_envelope(conn,org_id="org-org",project_id="dev-project",envelope=item,authorize=lambda c,r:True)==first
    assert conn.execute("SELECT count(*) FROM extension_runtime_binding").fetchone()[0]==0
    with conn.transaction():
        assert read_envelope(conn,org_id="org-org",project_id="dev-project",envelope_id=first,authorize=lambda c,r:True)==item
    with pytest.raises(RuntimeConflict):
        with conn.transaction():
            append_envelope(conn,org_id="org-org",project_id="dev-project",envelope=item.model_copy(update={"summary":"不同内容"}),authorize=lambda c,r:True)
    for permission in (False,None,1):
        with pytest.raises(PermissionError):
            with conn.transaction():read_envelope(conn,org_id="org-org",project_id="dev-project",envelope_id=first,authorize=lambda c,r:permission)
    assert conn.execute("SELECT count(*) FROM extension_audit_envelope").fetchone()[0]==1


def test_audit_cross_tenant_and_invalid_document_rejected(database):
    from aos_api.extension_runtime.audit_envelopes import append_envelope,read_envelope
    conn,role,_=database
    installation,_=seed(conn)
    item=envelope(installation)
    scoped(conn,role)
    with conn.transaction():
        identity=append_envelope(conn,org_id="org-org",project_id="dev-project",envelope=item,authorize=lambda c,r:True)
    with pytest.raises(PermissionError):
        with conn.transaction():read_envelope(conn,org_id="dev-org",project_id="dev-project",envelope_id=identity,authorize=lambda c,r:True)
    conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    with pytest.raises(LookupError):
        with conn.transaction():read_envelope(conn,org_id="dev-org",project_id="dev-project",envelope_id=identity,authorize=lambda c,r:True)
    with pytest.raises(ValueError):
        envelope_type=type(item)
        envelope_type.model_validate({**item.model_dump(),"business_title":"Technical-ID-001"})


def test_audit_linked_artifact_permission_is_rechecked(database):
    from aos_api.extension_runtime.audit_envelopes import append_envelope,read_envelope,ExactRef,AuditArtifact
    conn,role,_=database
    installation,_=seed(conn)
    item=envelope(installation)
    private=ExactRef(authority="artifact",id="private-result",revision=1,hash="sha256:"+"b"*64)
    item=item.model_copy(update={"artifacts":(AuditArtifact(ref=private,media_type="text/plain",size=12),)})
    scoped(conn,role)
    deny_artifact=lambda c,r:r.authority!="artifact"
    with pytest.raises(PermissionError):
        with conn.transaction():append_envelope(conn,org_id="org-org",project_id="dev-project",envelope=item,authorize=deny_artifact)
    with conn.transaction():identity=append_envelope(conn,org_id="org-org",project_id="dev-project",envelope=item,authorize=lambda c,r:True)
    with pytest.raises(PermissionError):
        with conn.transaction():read_envelope(conn,org_id="org-org",project_id="dev-project",envelope_id=identity,authorize=deny_artifact)


def test_audit_strict_version_and_size(database):
    from aos_api.extension_runtime.audit_envelopes import AuditEnvelope,ExactRef
    installation,_=seed(database[0])
    item=envelope(installation)
    with pytest.raises(ValueError):AuditEnvelope.model_validate({**item.model_dump(),"schema_version":True})
    refs=tuple(ExactRef(authority="task",id="长"*240,revision=i+1,hash="sha256:"+"a"*64) for i in range(64))
    with pytest.raises(ValueError):AuditEnvelope.model_validate({**item.model_dump(),"task_refs":refs,"run_refs":refs})
