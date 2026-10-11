"""Allowlisted membership aggregate, never authentication or publishing proof."""
import hashlib
import json
from pathlib import Path
import release_transition as T
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope

OUTPUT=T.R/'restored-identity-route-audit.json'

def inspect():
    T.H.preflight(T.R/'private/restored-identity.json')
    with T.factory() as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        apply_asset_transaction_scope(c,org_id='org-org',project_id='dev-project')
        columns=c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='meta_membership' ORDER BY ordinal_position").fetchall()
        names=[x['column_name'] for x in columns]
        assert {'org_id','project_id','subject','role'} <= set(names), 'MEMBERSHIP_SCHEMA_NOT_READABLE'
        rows=c.execute('SELECT subject,role FROM meta_membership WHERE org_id=%s AND project_id=%s ORDER BY subject,role',('org-org','dev-project')).fetchall()
        fingerprint=hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()
        roles={}
        for x in rows:roles[x['role']]=roles.get(x['role'],0)+1
        subjects={x['subject'] for x in rows}
        result={'tenant':{'orgId':'org-org','projectId':'dev-project'},'memberships':len(rows),'uniqueSubjects':len(subjects),'devSubjects':sum(x=='user:dev' for x in subjects),'nonDevSubjects':sum(x!='user:dev' for x in subjects),'roles':roles,'membershipFingerprint':fingerprint,'transactionReadOnly':c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']=='on','formalIdentityVerified':False,'formalPublisherVerified':False,'databaseWrites':0,'subjectValuesEmitted':False}
    return result

if __name__=='__main__':
    assert not OUTPUT.exists(),'Existing result: reconcile only'
    first=inspect();second=inspect();assert first==second
    first['independentConnectionAggregateExact']=True
    with OUTPUT.open('x') as f:json.dump(first,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(first,ensure_ascii=False))
