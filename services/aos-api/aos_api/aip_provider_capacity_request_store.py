"""Persist current Owner's unapproved terms; never activate physical capacity."""
import json
from datetime import timedelta
from uuid import uuid4
from aos_api.auth import Principal
from aos_api.db import connect_serializable
from aos_api.tenant_scope import TenantScope
from aos_api.aip_provider_capacity_authorization import ProviderCapacityRequest
from aos_api.aip_model_eval_request_store import AipModelEvalRequestStore, ModelEvalRequestBlocked
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractError


class ProviderCapacityRequestBlocked(RuntimeError):
    code='PROVIDER_CAPACITY_REQUEST_BLOCKED'


class ProviderCapacityRequestConflict(ProviderCapacityRequestBlocked):
    code='PROVIDER_CAPACITY_REQUEST_CONFLICT'


class ProviderCapacityRequestStore:
    def __init__(self, connect_factory=connect_serializable):
        self._connect_factory=connect_factory

    def create(self, scope, principal, idempotency_key, request):
        if (type(scope) is not TenantScope or scope.key!=('org-org','dev-project')
            or type(principal) is not Principal or principal.token_kind!='oidc'
            or (principal.org_id,principal.project_id)!=scope.key
            or type(request) is not ProviderCapacityRequest
            or any(type(value) is not str or not 1<=len(value)<=200 or value!=value.strip()
                   for value in (idempotency_key,principal.subject))):
            raise ProviderCapacityRequestBlocked('EXACT_OIDC_OWNER_REQUEST_REQUIRED')
        try:
            request=ProviderCapacityRequest.model_validate(request.model_dump(mode='python',by_alias=True))
        except (TypeError,ValueError) as exc:
            raise ProviderCapacityRequestBlocked('STRICT_CAPACITY_REQUEST_REQUIRED') from exc
        if (request.tenant.org_id,request.tenant.project_id)!=scope.key:
            raise ProviderCapacityRequestBlocked('REQUEST_SCOPE_REQUIRED')
        body={'application':request.model_dump(mode='json',by_alias=True),'makerSubject':principal.subject}
        with self._connect_factory(scope) as conn:
            identity=conn.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
                "current_setting('aos.project_id',true) AS project_id,"
                "current_setting('transaction_isolation') AS isolation").fetchone()
            if tuple(identity[key] for key in ('role','org_id','project_id','isolation')) != ('aos_runtime',*scope.key,'serializable'):
                raise ProviderCapacityRequestBlocked('SERIAL_TENANT_RUNTIME_REQUIRED')
            members=conn.execute('SELECT role FROM public.meta_membership WHERE org_id=%s AND project_id=%s '
                'AND subject=%s FOR SHARE',(*scope.key,principal.subject)).fetchall()
            if len(members)!=1 or members[0]['role'].lower()!='owner':
                raise ProviderCapacityRequestBlocked('CURRENT_OWNER_REQUIRED')
            now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            if not (request.valid_from<=now<request.proposal_expires_at<=min(request.valid_until,now+timedelta(minutes=15))):
                raise ProviderCapacityRequestBlocked('CURRENT_BOUNDED_REQUEST_WINDOW_REQUIRED')
            try:
                AipModelEvalRequestStore._current_revision(conn,scope,'provider',request.provider_ref)
                basis=AipProductionContractStore().get_evidence_bundle(scope,
                    request.basis_evidence_ref.asset_id,request.basis_evidence_ref.revision,conn=conn)
            except (ModelEvalRequestBlocked,ProductionContractError) as exc:
                raise ProviderCapacityRequestBlocked('CURRENT_PROVIDER_OR_BASIS_REQUIRED') from exc
            if (basis.content_hash!=request.basis_evidence_ref.content_hash
                or basis.lifecycle.value!='frozen' or basis.revoked):
                raise ProviderCapacityRequestBlocked('CURRENT_EXACT_BASIS_REQUIRED')
            digest=conn.execute("SELECT encode(public.digest(convert_to(public.canonical_asset_registry_jsonb(%s::jsonb),"
                "'UTF8'),'sha256'),'hex') AS hash",(json.dumps(body,ensure_ascii=False),)).fetchone()['hash']
            row=conn.execute('INSERT INTO public.aip_provider_capacity_request '
                '(org_id,project_id,request_id,idempotency_key,request_hash,request_json,created_by,expires_at) '
                'VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s) '
                'ON CONFLICT(org_id,project_id,idempotency_key) DO NOTHING RETURNING *',
                (*scope.key,'capacity-request-'+uuid4().hex,idempotency_key,digest,
                 json.dumps(body,ensure_ascii=False),principal.subject,request.proposal_expires_at)).fetchone()
            if row is None:
                row=conn.execute('SELECT * FROM public.aip_provider_capacity_request '
                    'WHERE org_id=%s AND project_id=%s AND idempotency_key=%s',(*scope.key,idempotency_key)).fetchone()
                if row is None or row['request_hash']!=digest or row['created_by']!=principal.subject:
                    raise ProviderCapacityRequestConflict('REQUEST_KEY_OR_MAKER_DRIFTED')
            conn.commit()
            return dict(row)
