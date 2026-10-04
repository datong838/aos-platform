"""Exact signed LicensePolicy bytes in the caller's current transaction.

Policy facts do not license an EvidenceBundle or authorize any runtime start.
"""
from dataclasses import dataclass,field
from datetime import datetime
import json
from typing import Any,Literal
from uuid import UUID

import psycopg

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_license_source_authority import _require_scope,LicenseSourceUnavailable
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.extension_runtime.current_installation_release_evidence import (
    SelectedReleaseEvidence,_read_exact_in_transaction,
)
from aos_api.tenant_scope import TenantScope

POLICY_PATH='content/policies/aip6-runtime-policies.json'
_SUPPORTED_RULES=frozenset({'source_license_required','derived_asset_traceable'})


class SignedLicensePolicyUnavailable(RuntimeError):
    pass


@dataclass(frozen=True,slots=True)
class SignedLicensePolicyFact:
    scope: tuple[str,str]
    installation_id: str
    installation_etag: int
    installation_revision: int
    release_ref: SelectedReleaseEvidence
    policy_ref: VersionedAssetRef
    rules: tuple[str,...]
    checked_at: datetime
    authorization: Literal['SIGNED_POLICY_EVIDENCE_ONLY_NO_START']=field(
        default='SIGNED_POLICY_EVIDENCE_ONLY_NO_START',init=False)


def _unique_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError('duplicate policy JSON key')
        result[key]=value
    return result


def _parse_license_policy(raw: bytes) -> tuple[str,tuple[str,...]]:
    try:
        document=json.loads(raw,object_pairs_hook=_unique_pairs)
        if (type(document) is not dict or set(document)!={'schemaVersion','artifacts'}
                or type(document['schemaVersion']) is not int or document['schemaVersion']!=1
                or type(document['artifacts']) is not list
                or any(type(entry) is not dict for entry in document['artifacts'])):
            raise ValueError('policy document schema')
        candidates=[entry for entry in document['artifacts'] if entry.get('assetType')=='LicensePolicy']
        if len(candidates)!=1:
            raise ValueError('policy entry ambiguous')
        entry=candidates[0]
        if (set(entry)!={'assetType','id','rules'} or type(entry['id']) is not str
                or not entry['id'] or entry['id']!=entry['id'].strip() or not entry['id'].isprintable()
                or type(entry['rules']) is not list
                or any(type(rule) is not str for rule in entry['rules'])
                or len(entry['rules'])!=len(set(entry['rules']))):
            raise ValueError('policy entry schema')
        if set(entry['rules'])!=_SUPPORTED_RULES:
            raise SignedLicensePolicyUnavailable('SIGNED_LICENSE_POLICY_RULES_UNSUPPORTED')
        return entry['id'],tuple(sorted(entry['rules']))
    except SignedLicensePolicyUnavailable:
        raise
    except (ValueError,TypeError,KeyError,UnicodeError):
        raise SignedLicensePolicyUnavailable('SIGNED_LICENSE_POLICY_DOCUMENT_INVALID') from None


def read_license_source_policy(*,conn: Any,scope: TenantScope,installation_id: str,
    expected_etag: int,release_ref: SelectedReleaseEvidence,policy_ref: VersionedAssetRef,
    release_policy: ReleasePolicy,loader: ManifestLoader) -> SignedLicensePolicyFact:
    try:
        _require_scope(conn,scope)
    except LicenseSourceUnavailable as exc:
        reason='SCOPE_MISMATCH' if str(exc)=='LICENSE_SOURCE_SCOPE_MISMATCH' else 'CALLER_TRANSACTION_REQUIRED'
        raise SignedLicensePolicyUnavailable('SIGNED_LICENSE_POLICY_'+reason) from None
    if conn.execute('SHOW transaction_isolation').fetchone()['transaction_isolation']!='serializable':
        raise SignedLicensePolicyUnavailable('SIGNED_LICENSE_POLICY_SERIALIZABLE_REQUIRED')
    if (type(installation_id) is not str or type(expected_etag) is not int or expected_etag<1
            or type(release_ref) is not SelectedReleaseEvidence
            or not isinstance(release_policy,ReleasePolicy) or not isinstance(loader,ManifestLoader)):
        raise SignedLicensePolicyUnavailable('SIGNED_LICENSE_POLICY_EXACT_INPUT_REQUIRED')
    try:
        if str(UUID(installation_id))!=installation_id:
            raise ValueError('noncanonical installation')
    except (ValueError,TypeError,AttributeError):
        raise SignedLicensePolicyUnavailable('SIGNED_LICENSE_POLICY_EXACT_INPUT_REQUIRED') from None
    if (type(policy_ref) is not VersionedAssetRef or policy_ref.asset_type!='LicensePolicy'
            or type(policy_ref.revision) is not int or policy_ref.revision!=1):
        raise SignedLicensePolicyUnavailable('SIGNED_LICENSE_POLICY_EXACT_POLICY_REF_REQUIRED')
    try:
        view,row,records=_read_exact_in_transaction(conn,scope=scope,exact_installation=installation_id,
            release_policy=release_policy,loader=loader)
    except (psycopg.errors.SerializationFailure,psycopg.errors.DeadlockDetected):
        raise
    except Exception:
        raise SignedLicensePolicyUnavailable('SIGNED_LICENSE_POLICY_RELEASE_UNAVAILABLE') from None
    if view.etag_version!=expected_etag or row['state']!='active' or view.active_revision!=view.current_revision:
        raise SignedLicensePolicyUnavailable('SIGNED_LICENSE_POLICY_INSTALLATION_DRIFT')
    if release_ref not in view.releases:
        raise SignedLicensePolicyUnavailable('SIGNED_LICENSE_POLICY_RELEASE_NOT_SELECTED')
    selected_records=[entry for entry in records if
        (entry[0].publisher,entry[0].id,entry[0].version,entry[0].content_hash)==
        (release_ref.publisher,release_ref.bundle_id,release_ref.version,release_ref.content_hash)]
    if len(selected_records)!=1:
        raise SignedLicensePolicyUnavailable('SIGNED_LICENSE_POLICY_RELEASE_NOT_SELECTED')
    selected,record,source_ref=selected_records[0]
    try:
        loaded=loader.load(source_ref)
        if (loaded.content_hash!=selected.content_hash or loaded.manifest!=record.manifest
                or loaded.signature!=record.signature):
            raise ValueError('release bytes changed')
        artifacts=[item for item in loaded.artifacts if item.relative_path==POLICY_PATH]
        if len(artifacts)!=1:
            raise ValueError('policy artifact missing or ambiguous')
        artifact=artifacts[0]
        if policy_ref.content_hash!=artifact.digest.removeprefix('sha256:'):
            raise SignedLicensePolicyUnavailable('SIGNED_LICENSE_POLICY_HASH_DRIFT')
        raw=loader.read_verified_artifact(source_ref,POLICY_PATH,expected_digest=artifact.digest,limit=262144)
    except SignedLicensePolicyUnavailable:
        raise
    except Exception:
        raise SignedLicensePolicyUnavailable('SIGNED_LICENSE_POLICY_BYTES_UNAVAILABLE') from None
    identifier,rules=_parse_license_policy(raw)
    if identifier!=policy_ref.asset_id:
        raise SignedLicensePolicyUnavailable('SIGNED_LICENSE_POLICY_ID_DRIFT')
    return SignedLicensePolicyFact(scope.key,installation_id,view.etag_version,view.current_revision,
        release_ref,policy_ref.model_copy(deep=True),rules,view.checked_at)
