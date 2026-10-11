"""Same-transaction media Source validation; never grants execution authority."""
from __future__ import annotations
from contextlib import contextmanager
import re
from psycopg import Connection, IsolationLevel
from psycopg.pq import TransactionStatus
from pydantic import ValidationError
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.contracts import BundleKind
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.registry_service import RegistryService, _VersionRecord
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.extension_runtime.current_installation_release_evidence import (
    _read_unique_active_in_transaction, CurrentReleaseEvidenceBlocked,
)
from aos_api.extension_runtime.configuration_stage_preflight import configuration_source_acl_ready
from aos_api.extension_runtime.ui_resources import _source_ref
from aos_api.aip_media_gate_policy_contribution import MediaGatePolicyContribution
from aos_api.aip_production_contracts import RegisterMediaGateProfileRequest, ExactRevisionRef
from aos_api.aip_production_contract_store import (
    AipProductionContractStore, ProductionContractDependencyBlocked, ProductionContractNotFound,
)
from aos_api.tenant_scope import TenantScope
from aos_api.aip_bi_plan_issuer_connection import _ScopedBIIssuerConnection


class _InvalidSourceDigest(ValueError):
    pass


def _bare(digest):
    if not isinstance(digest,str) or re.fullmatch(r'sha256:[0-9a-f]{64}',digest) is None:
        raise _InvalidSourceDigest('canonical Source digest required')
    return digest.removeprefix('sha256:')


class CompleteMediaGateSourceReader:
    """Use trusted server dependencies; callers cannot supply paths or approval."""
    def __init__(self, *, loader: ManifestLoader,
                 policy_relative_path: str='content/media-gate-policies/full.json'):
        if not isinstance(loader,ManifestLoader):raise TypeError('original ManifestLoader required')
        self.loader=loader
        self.policy_relative_path=policy_relative_path

    def __call__(self,conn,scope,body):
        # The original write connector preserves tenant scope across Store
        # commits with this exact wrapper. Inspect its same native transaction;
        # keep all database identity/ACL checks below, without duck typing.
        if type(conn) is _ScopedBIIssuerConnection:
            conn = conn._raw
        if (not isinstance(conn,Connection) or type(scope) is not TenantScope
            or not isinstance(body,RegisterMediaGateProfileRequest)
            or conn.info.transaction_status != TransactionStatus.INTRANS
            or conn.isolation_level != IsolationLevel.SERIALIZABLE or conn.read_only is not False):
            return False
        identity=conn.execute("""SELECT session_user AS login,current_user AS role,
            current_setting('aos.org_id',true) AS org,current_setting('aos.project_id',true) AS project,
            pg_has_role(current_user,'aos_runtime','member') AS runtime_member,
            transaction_timestamp() AS checked_at""").fetchone()
        if (identity['login']!='aos_contract_source_issuer' or identity['role']!=identity['login']
            or (identity['org'],identity['project'])!=scope.key or identity['runtime_member'] is not False):
            return False
        if configuration_source_acl_ready(conn) is not True:return False
        coordinate=body.source_bundle_ref.resource_id
        pieces=coordinate.rsplit('@',1)
        if len(pieces)!=2 or len(pieces[0].split('/'))!=2:return False
        publisher,bundle_id=pieces[0].split('/');version=pieces[1]
        @contextmanager
        def existing_transaction():yield conn
        store=PostgresRegistryStore(existing_transaction)
        service=RegistryService(store=store,loader=self.loader,trust_roots=self.loader.trust_roots,
            clock=lambda:identity['checked_at'])
        try:
            material=service.get_published_reference_material(bundle_id=bundle_id,version=version,publisher=publisher)
            if type(material['publicationSequence']) is not int:return False
            manifest_ref=ExactRevisionRef(resourceType='BundleManifestRevision',resourceId=coordinate,
                revision=material['publicationSequence'],contentHash=_bare(material['contentHash']))
            signature_ref=ExactRevisionRef(resourceType='BundleSignatureVerification',resourceId=coordinate,
                revision=material['publicationSequence'],contentHash=_bare(material['signatureFingerprint']))
            if body.source_bundle_ref!=manifest_ref or body.signature_ref!=signature_ref:return False
            record=_VersionRecord.from_store(store.get_version(bundle_id,version,publisher))
            source_ref=_source_ref(record)
            if source_ref is None:return False
            loaded=self.loader.load(source_ref)
            if (loaded.manifest.kind!=BundleKind.SOLUTION_PACK or loaded.content_hash!=material['contentHash']
                or loaded.manifest!=record.manifest or loaded.signature!=record.signature):return False
            view=_read_unique_active_in_transaction(conn,scope=scope,publisher=publisher,
                bundle_id=bundle_id,version=version,content_hash=material['contentHash'],
                release_policy=ReleasePolicy(trust_roots=self.loader.trust_roots),loader=self.loader)
            if view.scope!=scope.key or view.active_revision!=view.current_revision:return False
            matched=[r for r in view.releases if (r.publisher,r.bundle_id,r.version,r.content_hash)==
                (publisher,bundle_id,version,material['contentHash'])]
            if (len(matched)!=1 or matched[0].signature_fingerprint!=material['signatureFingerprint']
                or matched[0].release_evidence_revision!=material['releaseEvidenceRevision']):return False
            artifacts=[a for a in loaded.artifacts if a.relative_path==self.policy_relative_path]
            if len(artifacts)!=1:return False
            raw=self.loader.read_verified_artifact(source_ref,self.policy_relative_path,
                expected_digest=artifacts[0].digest,limit=32768)
            contribution=MediaGatePolicyContribution.model_validate_json(raw)
            policy_ref=ExactRevisionRef(resourceType='MediaGatePolicyRevision',
                resourceId=coordinate+'#'+contribution.policy_id,revision=contribution.revision,
                contentHash=_bare(artifacts[0].digest))
            gates=lambda items:sorted((g.model_dump(mode='json',by_alias=True) for g in items),key=lambda x:x['gateId'])
            if (body.policy_ref!=policy_ref or body.profile_id!=contribution.profile_id
                or body.revision!=contribution.profile_revision or gates(body.gates)!=gates(contribution.gates)):
                return False
            def no_connection(_):raise RuntimeError('caller transaction required')
            rules=AipProductionContractStore(no_connection)
            for gate in contribution.gates:
                rule=rules.get_review_rule_revision_with_content_integrity(scope,gate.rule_ref,conn=conn)
                if rule.spec.get('testOnly') is not False:return False
                receipt=conn.execute("""SELECT result_ref,request_hash,created_by
                    FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s
                    AND operation='review_rule.register' AND result_ref->>'resourceId'=%s
                    AND result_ref->>'revision'=%s AND result_ref->>'contentHash'=%s""",
                    (*scope.key,gate.rule_ref.resource_id,str(gate.rule_ref.revision),gate.rule_ref.content_hash)).fetchall()
                expected=gate.rule_ref.model_dump(mode='json',by_alias=True)
                if not any(r['result_ref']==expected and r['request_hash']==rule.content_hash
                    and r['created_by']==rule.created_by for r in receipt):return False
            return True
        except (AssetRegistryError,CurrentReleaseEvidenceBlocked,ValidationError,_InvalidSourceDigest,
                ProductionContractDependencyBlocked,ProductionContractNotFound):
            return False
