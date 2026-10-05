"""Produce unverified candidates. No formal account mapping, source grant or reservation."""
import json
from uuid import uuid4

from aos_api.auth import Principal
from aos_api.db import connect_serializable
from aos_api.tenant_scope import TenantScope
from aos_api.aip_model_eval_request_store import AipModelEvalRequestStore,ModelEvalRequestBlocked
from aos_api.aip_production_contract_store import AipProductionContractStore,ProductionContractError
from aos_api.aip_provider_capacity_source_contracts import ProviderPhysicalAccountCandidate,ProviderCapacityBasisCandidate


class ProviderCapacityCandidateBlocked(RuntimeError):
    pass


class ProviderCapacityCandidateConflict(ProviderCapacityCandidateBlocked):
    pass


class ProviderCapacityCandidateStore:
    def __init__(self,connect_factory=connect_serializable):
        self._connect_factory=connect_factory

    def create_account(self,scope,principal,key,candidate):
        return self._create(scope,principal,key,candidate,'account',ProviderPhysicalAccountCandidate)

    def create_basis(self,scope,principal,key,candidate):
        return self._create(scope,principal,key,candidate,'basis',ProviderCapacityBasisCandidate)

    @staticmethod
    def _account_dependencies(conn,scope,candidate):
        for ref in sorted(candidate.provider_refs,key=lambda item:item.asset_id):
            AipModelEvalRequestStore._current_revision(conn,scope,'provider',ref)
        ProviderCapacityCandidateStore._evidence(conn,scope,candidate.evidence_ref)

    @staticmethod
    def _evidence(conn,scope,ref):
        item=AipProductionContractStore().get_evidence_bundle(scope,ref.asset_id,ref.revision,conn=conn)
        if item.content_hash!=ref.content_hash or item.lifecycle.value!='frozen' or item.revoked:
            raise ProviderCapacityCandidateBlocked('CURRENT_EXACT_EVIDENCE_REQUIRED')

    def _create(self,scope,principal,key,candidate,kind,model):
        if (type(scope) is not TenantScope or scope.key!=('org-org','dev-project')
            or type(principal) is not Principal or principal.token_kind!='oidc'
            or (principal.org_id,principal.project_id)!=scope.key or type(candidate) is not model
            or any(type(value) is not str or not 1<=len(value)<=200 or value!=value.strip()
                   for value in (key,principal.subject))):
            raise ProviderCapacityCandidateBlocked('EXACT_OWNER_CANDIDATE_REQUIRED')
        try:candidate=model.model_validate(candidate.model_dump(mode='python',by_alias=True))
        except (TypeError,ValueError) as exc:
            raise ProviderCapacityCandidateBlocked('STRICT_CANDIDATE_REQUIRED') from exc
        body={'candidateKind':kind,'candidate':candidate.model_dump(mode='json',by_alias=True),'makerSubject':principal.subject}
        with self._connect_factory(scope) as conn:
            identity=conn.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
                "current_setting('aos.project_id',true) AS project_id,current_setting('transaction_isolation') AS isolation").fetchone()
            if tuple(identity[name] for name in ('role','org_id','project_id','isolation'))!=('aos_runtime',*scope.key,'serializable'):
                raise ProviderCapacityCandidateBlocked('SERIAL_TENANT_RUNTIME_REQUIRED')
            members=conn.execute('SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE',
                (*scope.key,principal.subject)).fetchall()
            if len(members)!=1 or members[0]['role'].lower()!='owner':
                raise ProviderCapacityCandidateBlocked('CURRENT_OWNER_REQUIRED')
            try:
                if kind=='account':self._account_dependencies(conn,scope,candidate)
                else:
                    ref=candidate.physical_account_ref
                    account=conn.execute("SELECT *,encode(public.digest(convert_to(public.canonical_asset_registry_jsonb(request_json),'UTF8'),'sha256'),'hex') AS actual_hash "
                        "FROM aip_provider_capacity_candidate WHERE org_id=%s AND project_id=%s AND candidate_id=%s AND revision=%s AND candidate_kind='account'",
                        (*scope.key,ref.asset_id,ref.revision)).fetchone()
                    if (account is None or account['content_hash']!=ref.content_hash or account['actual_hash']!=ref.content_hash
                        or account['basis_verified'] is not False or account['execution_allowed'] is not False
                        or account['request_json'].get('makerSubject')!=account['created_by']):
                        raise ProviderCapacityCandidateBlocked('EXACT_ACCOUNT_CANDIDATE_REQUIRED')
                    parent=ProviderPhysicalAccountCandidate.model_validate(account['request_json']['candidate'])
                    self._account_dependencies(conn,scope,parent)
                self._evidence(conn,scope,candidate.evidence_ref)
            except (ModelEvalRequestBlocked,ProductionContractError,TypeError,ValueError) as exc:
                raise ProviderCapacityCandidateBlocked('CURRENT_CANDIDATE_DEPENDENCY_REQUIRED') from exc
            digest=conn.execute("SELECT encode(public.digest(convert_to(public.canonical_asset_registry_jsonb(%s::jsonb),'UTF8'),'sha256'),'hex') AS hash",
                (json.dumps(body,ensure_ascii=False),)).fetchone()['hash']
            row=conn.execute("INSERT INTO aip_provider_capacity_candidate(org_id,project_id,candidate_id,candidate_kind,idempotency_key,content_hash,request_json,created_by) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s) ON CONFLICT(org_id,project_id,idempotency_key) DO NOTHING RETURNING *",
                (*scope.key,'capacity-candidate-'+uuid4().hex,kind,key,digest,json.dumps(body,ensure_ascii=False),principal.subject)).fetchone()
            if row is None:
                row=conn.execute('SELECT * FROM aip_provider_capacity_candidate WHERE org_id=%s AND project_id=%s AND idempotency_key=%s',(*scope.key,key)).fetchone()
                if row is None or row['content_hash']!=digest or row['created_by']!=principal.subject or row['candidate_kind']!=kind:
                    raise ProviderCapacityCandidateConflict('CANDIDATE_KEY_OR_MAKER_DRIFTED')
            conn.commit()
            return dict(row)
