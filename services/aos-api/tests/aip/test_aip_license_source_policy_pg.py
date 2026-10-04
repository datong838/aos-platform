"""Actual signed-installation Policy facts; no license issuer or start grant."""
from dataclasses import replace
import json

import psycopg
from psycopg import IsolationLevel
from psycopg.rows import dict_row
import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.db import get_dsn
from aos_api.tenant_scope import TenantScope,apply_transaction_scope
from aos_api.extension_runtime.current_installation_release_evidence import _read_exact_in_transaction

SCOPE=TenantScope('org-org','dev-project')
PATH='content/policies/aip6-runtime-policies.json'


def assert_active_signed_license_policy(installation_id,loader,release_policy):
    from aos_api.aip_license_source_policy import read_license_source_policy,SignedLicensePolicyUnavailable
    with psycopg.connect(get_dsn(),row_factory=dict_row) as conn:
        conn.isolation_level=IsolationLevel.SERIALIZABLE
        apply_transaction_scope(conn,SCOPE)
        view,row,records=_read_exact_in_transaction(conn,scope=SCOPE,
            exact_installation=installation_id,release_policy=release_policy,loader=loader)
        assert view.active_revision==view.current_revision and row['state']=='active'
        release=next(item for item in view.releases if item.bundle_id=='solution.ecommerce.growth')
        selected,record,source_ref=next(entry for entry in records if entry[0].id==release.bundle_id)
        loaded=loader.load(source_ref)
        artifact=next(item for item in loaded.artifacts if item.relative_path==PATH)
        document=json.loads(loader.read_verified_artifact(source_ref,PATH,expected_digest=artifact.digest,limit=262144))
        entry=next(item for item in document['artifacts'] if item['assetType']=='LicensePolicy')
        ref=VersionedAssetRef(asset_type='LicensePolicy',asset_id=entry['id'],revision=1,content_hash=artifact.digest.removeprefix('sha256:'))
        args=dict(conn=conn,scope=SCOPE,installation_id=installation_id,
                  expected_etag=view.etag_version,release_ref=release,policy_ref=ref,
                  release_policy=release_policy,loader=loader)
        fact=read_license_source_policy(**args)
        assert fact.authorization=='SIGNED_POLICY_EVIDENCE_ONLY_NO_START'
        assert fact.policy_ref==ref and fact.release_ref==release
        assert fact.installation_etag==view.etag_version
        assert fact.rules==('derived_asset_traceable','source_license_required')
        assert release.version=='1.13.0', 'current actual signed release, not static candidate 1.11'
        for changed,reason in (
            ({'expected_etag':view.etag_version+1},'INSTALLATION_DRIFT'),
            ({'policy_ref':ref.model_copy(update={'content_hash':'d'*64})},'POLICY_HASH_DRIFT'),
            ({'policy_ref':ref.model_copy(update={'asset_type':'LicensePolicyRevision'})},'EXACT_POLICY_REF_REQUIRED'),
            ({'policy_ref':ref.model_copy(update={'asset_id':'wrong-policy'})},'POLICY_ID_DRIFT'),
            ({'policy_ref':ref.model_copy(update={'revision':2})},'EXACT_POLICY_REF_REQUIRED'),
            ({'release_ref':replace(release,version='1.11.0')},'RELEASE_NOT_SELECTED'),
            ({'scope':TenantScope('dev-org','dev-project')},'SCOPE_MISMATCH'),
        ):
            with pytest.raises(SignedLicensePolicyUnavailable,match=reason):
                read_license_source_policy(**{**args,**changed})
        # Preserve a known precommit transaction conflict instead of masking it
        # as missing Policy. Fault injection never returns a fake signed success.
        import aos_api.aip_license_source_policy as module
        original=module._read_exact_in_transaction
        def fail_transaction(*args,**kwargs):
            raise psycopg.errors.SerializationFailure('b86 policy transaction conflict')
        module._read_exact_in_transaction=fail_transaction
        try:
            with pytest.raises(psycopg.errors.SerializationFailure):
                read_license_source_policy(**args)
        finally:
            module._read_exact_in_transaction=original
    with psycopg.connect(get_dsn(),row_factory=dict_row) as conn:
        apply_transaction_scope(conn,SCOPE)
        with pytest.raises(SignedLicensePolicyUnavailable,match='SERIALIZABLE_REQUIRED'):
            read_license_source_policy(**{**args,'conn':conn})


@pytest.mark.parametrize('raw,reason',[
    (b'{"schemaVersion":true,"artifacts":[]}', 'DOCUMENT_INVALID'),
    (b'{"schemaVersion":2,"artifacts":[]}', 'DOCUMENT_INVALID'),
    (b'{"schemaVersion":1,"schemaVersion":1,"artifacts":[]}', 'DOCUMENT_INVALID'),
    (b'{"schemaVersion":1,"artifacts":[]}', 'DOCUMENT_INVALID'),
    (b'{"schemaVersion":1,"artifacts":[{"assetType":"LicensePolicy","id":"x","rules":["source_license_required","source_license_required"]}]}', 'DOCUMENT_INVALID'),
    (b'{"schemaVersion":1,"artifacts":[{"assetType":"LicensePolicy","id":"x","rules":["source_license_required"]}]}', 'RULES_UNSUPPORTED'),
    (b'{"schemaVersion":1,"artifacts":[{"assetType":"LicensePolicy","id":"x","rules":["source_license_required","derived_asset_traceable","require_independent_license_grant"]}]}', 'RULES_UNSUPPORTED'),
    (b'{"schemaVersion":1,"artifacts":[{"assetType":"LicensePolicy","id":"x","rules":[]},{"assetType":"LicensePolicy","id":"y","rules":[]}]}', 'DOCUMENT_INVALID'),
    (b'{"schemaVersion":1,"artifacts":[{"assetType":"LicensePolicy","id":"x","rules":["source_license_required","derived_asset_traceable"],"allowAll":true}]}', 'DOCUMENT_INVALID'),
])
def test_policy_schema_or_rule_change_cannot_silently_widen_interpretation(raw,reason):
    from aos_api.aip_license_source_policy import _parse_license_policy,SignedLicensePolicyUnavailable
    with pytest.raises(SignedLicensePolicyUnavailable,match=reason):
        _parse_license_policy(raw)
