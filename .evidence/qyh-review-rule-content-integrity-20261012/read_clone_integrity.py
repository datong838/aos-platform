"""Validate one preexisting isolated Rule; never approve it for production."""
from pathlib import Path
import sys,json,subprocess
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/aos-api'))
import psycopg
from psycopg.rows import dict_row
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.tenant_scope import TenantScope


def main():
    output=Path(__file__).parent/'live-clone-readback.json';assert not output.exists(),'Existing evidence: read-only reconciliation only'
    restored=json.loads((ROOT/'.evidence/qyh-source-boundary-clone-20261011/restore-verified.json').read_text())
    meta=json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect','--format','{"Id":{{json .Id}},"Mounts":{{json .Mounts}}}','qyh-source-boundary-clone-20261011'],text=True))
    assert meta['Id']==restored['container']['Id'] and not meta['Mounts']
    scope=TenantScope('org-org','dev-project')
    with psycopg.connect(host='127.0.0.1',port=18431,dbname='qyh_source_contract_20261011',user='aos_app',row_factory=dict_row) as conn:
        conn.read_only=True
        cluster=conn.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster'];assert cluster==restored['cloneIdentity']['cluster']
        row=conn.execute("SELECT rule_id,revision,content_hash FROM aip_review_rule_revision WHERE org_id=%s AND project_id=%s AND created_by='clone:test' ORDER BY rule_id,revision LIMIT 1",scope.key).fetchone();assert row
        ref=ExactRevisionRef(resourceType='EvalRuleRevision',resourceId=row['rule_id'],revision=row['revision'],contentHash=row['content_hash'])
        def forbidden(_):raise AssertionError('reader opened another transaction')
        store=AipProductionContractStore(forbidden)
        value=store.get_review_rule_revision_with_content_integrity(scope,ref,conn=conn)
        assert value.content_hash==ref.content_hash
    report={'outcome':'EXISTING_ISOLATED_RULE_CONTENT_INTEGRITY_VERIFIED','exactCloneIdentityVerified':True,'callerTransactionUsed':True,'existingRuleContentDigestExact':True,'newRuleCreated':False,'databaseWrites':0,'currentAuthoritativeDatabaseConnected':False,'canonicalProductionRuleAccepted':False,'signedMediaSourceAccepted':False}
    with output.open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))

if __name__=='__main__':main()
