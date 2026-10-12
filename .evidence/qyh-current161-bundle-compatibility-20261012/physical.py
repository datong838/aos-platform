"""Original signed compatibility artifact and physical verifier on live readbacks."""
import importlib.util
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    assert not (OUT/'physical-intent.json').exists(), 'Reconcile old verification before retry'
    audit=load('compat_audit',OUT/'audit.py')
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    verifier=load('original_schema_verifier',ROOT/'scripts/a0v_ecommerce_schema_receipts.py')
    config=Config(str(audit.FROZEN/'alembic.ini'))
    config.set_main_option('script_location',str(audit.FROZEN/'alembic'))
    graph=ScriptDirectory.from_config(config)
    assert graph.get_heads()==['a0v_161']
    revisions=lambda head:{r.revision for r in graph.walk_revisions(base='base',head=head)}
    common=ROOT/'.evidence/qyh-full-system-restoration-20261011'
    trust=audit.FileTrustRootProvider(common/'restoration-public-trust-roots.json').snapshot()
    loader=audit.ManifestLoader({'current':common/'selected-public-bundles'},trust_roots=trust)
    rows=[]
    for item in json.loads((common/'selected-public-root-terminal.json').read_text())['versions']:
        ref='bundle://current/'+item['id']+'/'+item['version']
        bundle=loader.load(ref)
        assert bundle.content_hash==item['contentHash']
        if bundle.manifest.spec.runtime is None:continue
        record=load('candidate_builder',ROOT/'scripts/build_ecommerce_runtime_candidates.py')._release_record(bundle)
        items=[r for r in record.artifacts if r['relativePath']=='artifacts/schema-compatibility.json']
        assert len(items)==1
        raw=loader.read_verified_artifact(ref,'artifacts/schema-compatibility.json',expected_digest=items[0]['digest'],limit=65536)
        doc=json.loads(raw)
        assert doc['bundleId']==item['id'] and doc['schemaVersion']==1
        rows.append((item['id'],doc,items[0]['digest']))
    assert len(rows)==3
    audit.save('physical-intent.json',{'signedCompatibilityArtifacts':3,'originalVerifierUsed':True,'databaseWrites':0})
    results=[]
    for container,db,label in [('qyh-restored-pg-20261011','aos_meta_head','physical-source159'),
                              ('qyh-current159-exact-restore-20261012','qyh_current160_fresh_rehearsal_20261012','physical-owned161')]:
        conn=audit.NativeReadTransaction(container,db,label)
        try:
            for bid,doc,digest in rows:
                verifier.verify_physical(conn,doc,revisions)
                altered={**doc,'requiredRelations':doc['requiredRelations']+['public.qyh_nonexistent_relation_negative_probe']}
                try:verifier.verify_physical(conn,altered,revisions)
                except ValueError as error:
                    assert 'required physical relation is missing' in str(error)
                else:raise AssertionError('Physical missing relation was accepted')
                results.append({'database':db,'bundleId':bid,'signedArtifactDigest':digest,
                    'requiredRevision':doc['alembicRevision'],'requiredRelationCount':len(doc['requiredRelations']),
                    'originalPhysicalVerifierPassed':True,'missingRelationRejected':True,'readonly':True})
        finally:conn.close()
    audit.save('physical-result.json',{'results':results,'sourceAndOwnedReadOnly':True,
        'actualSchemaReceiptWrites':0,'actualSourceMigrated':False,'actualBundleInstallationAccepted':False})
    print(json.dumps({'signedPhysicalCompatibilityChecks':len(results),'missingRelationNegativeChecks':len(results),'sourceWrites':0}),flush=True)


if __name__=='__main__': main()
