"""Prepare Growth after a reconciled Core publish rejection; never publish."""
import json
from datetime import UTC, datetime
import release_transition as T

if __name__ == '__main__':
    R=T.R
    assert not (R/'growth-independent-preparation-intent.json').exists(), 'Existing intent: reconcile only'
    reconciliation=json.loads((R/'registry-transition-readonly-reconciliation.json').read_text())
    assert reconciliation['outcome']=='PUBLISH_DUTY_SEPARATION_REJECTION_RECONCILED'
    assert reconciliation['unknownWriteResult'] is False
    identity=T.H.preflight(R/'private/restored-identity.json')
    store=T.PostgresRegistryStore(connect_factory=T.factory)
    core=store.get_version('domain.ecommerce.core','1.4.3',publisher='aos')
    assert core['status']=='validated' and core['createdBy']==T.ACTOR
    assert not any(e['toStatus']=='published' for e in core['lifecycleEvents'])
    try:
        store.get_version('solution.ecommerce.growth','1.13.0',publisher='aos')
    except T.AssetNotFoundError:
        pass
    else:
        raise RuntimeError('Growth exists: reconcile only')
    trust=T.FileTrustRootProvider(T.TRUST).snapshot()
    loader=T.ManifestLoader({'a0v-canonical':T.LEGACY_ROOT,'a0v-qyh-current':T.CURRENT/'signed-bundles'},trust_roots=trust)
    bundle=loader.load('bundle://a0v-qyh-current/solution.ecommerce.growth/1.13.0')
    T.ReleasePolicy(trust_roots=trust).evaluate(T.OLD._load_builder()._release_record(bundle),checked_at=datetime.now(UTC))
    assert len(bundle.workshop_modules)==7
    store.get_bundle('solution.ecommerce.growth',publisher='aos')
    def clock():
        with T.factory() as conn:return conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    service=T.RegistryService(store=store,loader=loader,clock=clock,trust_roots=trust)
    T.record('growth-independent-preparation-intent.json',{'id':'solution.ecommerce.growth','version':'1.13.0',
        'contentHash':bundle.content_hash,'coreStatus':'validated','actions':['create','validate'],
        'publishActionIncluded':False,'actor':T.ACTOR,'identity':identity['identity']})
    result=service.create_version(publisher='aos',bundle_id='solution.ecommerce.growth',source_ref=bundle.source_ref,
        actor=T.ACTOR,roles=T.OLD.REGISTRY_CREATE_ROLES,publisher_scopes=T.OLD.PUBLISHER_SCOPES)
    T.record('growth-independent-create-terminal.json',{'status':result['status'],'contentHash':result['contentHash']})
    result=service.validate(publisher='aos',bundle_id='solution.ecommerce.growth',version='1.13.0',
        actor=T.ACTOR,roles=T.OLD.REGISTRY_CREATE_ROLES,publisher_scopes=T.OLD.PUBLISHER_SCOPES)
    T.OLD.assert_registry_version_exact(result,T.OLD._expected_registry_version(bundle))
    assert result['status']=='validated'
    T.record('growth-independent-validate-terminal.json',{'outcome':'GROWTH113_CURRENT_VALIDATED_NO_PUBLISH',
        'status':result['status'],'contentHash':result['contentHash'],'runtimeAuthority':False,'providerInvocations':0})
    print('GROWTH113_CURRENT_VALIDATED_NO_PUBLISH')
