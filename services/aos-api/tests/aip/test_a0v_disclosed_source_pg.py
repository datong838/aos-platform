import os
import json
import pytest
from psycopg import sql
from test_aip_budget_reservation_pg import database, runtime_connection
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractDependencyBlocked, ProductionContractNotFound, canonical_hash
from aos_api.aip_production_contracts import ResolveEvidenceDisclosureRequest, RevokeEvidenceRequest
from aos_api.tenant_scope import TenantScope

pytestmark = pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST') != '1', reason='isolated PostgreSQL opt-in')


def test_disclosed_source_real_receipt_policy_and_revocation(database):
    payload = {"summary": "synthetic complete source", "marking": ["public"]}
    source_hash = canonical_hash(payload)
    tables = ['aip_evidence', 'aip_evidence_revoke_event', 'aip_evidence_bundle_revision',
              'aip_evidence_bundle_revoke_event', 'aip_evidence_disclosure_decision',
              'aip_production_contract_receipt']
    for table in tables:
        ident = sql.Identifier(table)
        database.owner.execute(sql.SQL('CREATE TABLE {} (LIKE public.{} INCLUDING ALL)').format(ident, ident))
        database.owner.execute(sql.SQL('GRANT SELECT,INSERT ON {} TO aos_runtime').format(ident))
        database.owner.execute(sql.SQL('ALTER TABLE {} ENABLE ROW LEVEL SECURITY').format(ident))
        database.owner.execute(sql.SQL('ALTER TABLE {} FORCE ROW LEVEL SECURITY').format(ident))
        database.owner.execute(sql.SQL("CREATE POLICY source_scope ON {} TO aos_runtime USING (org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK (org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(ident))
    database.owner.execute("""INSERT INTO aip_evidence(org_id,project_id,evidence_id,evidence_type,subject_ref,source_type,source_ref,observed_at,freshness_at,content_hash,payload,created_by)
        VALUES('org-org','dev-project','ev-source','query','{}','database','synthetic',now(),now(),%s,%s::jsonb,'actor')""", (source_hash, json.dumps(payload)))
    scope = TenantScope('org-org', 'dev-project')
    factory = runtime_connection(database)
    store = AipProductionContractStore(factory)
    body = ResolveEvidenceDisclosureRequest.model_validate({
        'evidenceRef': {'resourceType':'Evidence','resourceId':'ev-source','revision':1,'contentHash':source_hash},
        'purpose':'source','requestedLevel':'l3','taskId':'task-source',
    })
    decision = store.resolve_evidence_disclosure(scope,'actor','disclose-source',body,markings=['public','secret'])
    assert decision.status.value == 'allowed'
    with factory(scope) as conn:
        result = store.read_disclosed_evidence_source(conn,scope,'actor',decision.decision_id,body,markings=['public','secret'])
        assert result['payload']['summary'] == 'synthetic complete source'
        with pytest.raises(ProductionContractDependencyBlocked):
            store.read_disclosed_evidence_source(conn,scope,'actor',decision.decision_id,body.model_copy(update={'task_id':'other'}),markings=['public','secret'])
    canary = TenantScope('dev-org','dev-project')
    with factory(canary) as conn:
        with pytest.raises(ProductionContractNotFound):
            store.read_disclosed_evidence_source(conn,canary,'actor',decision.decision_id,body,markings=['public','secret'])
    store.revoke_evidence(scope,'actor','ev-source','revoke-source',RevokeEvidenceRequest.model_validate({'expectedContentHash':source_hash,'reason':'synthetic withdrawal'}))
    with factory(scope) as conn:
        with pytest.raises(ProductionContractDependencyBlocked):
            store.read_disclosed_evidence_source(conn,scope,'actor',decision.decision_id,body,markings=['public','secret'])
