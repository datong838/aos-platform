"""Default-off Route finalization proof contracts; never an executor."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import Field,field_validator,model_validator

from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.aip_budget_reservation_contracts import exact_ref_payload
from aos_api.aip_contracts import AipContractModel,TenantContext
from aos_api.aip_model_route_eval_signatures import (
    GovernedEvalIssuerInput,GovernedEvalSignedCase,GovernedEvalSignedCertificate,
)
from aos_api.aip_model_runtime_store import canonical_hash
from aos_api.tenant_scope import TenantScope


SHA=r'^[0-9a-f]{64}$'


class RouteEvalFinalizationConflict(RuntimeError):
    """Fail-closed category for Route finalization proof drift."""


def _hash(value) -> str:
    return canonical_hash(value.model_dump(mode='json',by_alias=True))


class RouteEvalFinalizedCallProof(AipContractModel):
    schema_version: Literal['aos.route-eval-finalized-call-proof/v1']='aos.route-eval-finalized-call-proof/v1'
    tenant: TenantContext
    execution_id: str=Field(min_length=1,max_length=200)
    case_id: str=Field(min_length=1,max_length=200)
    purpose: Literal['target','judge']
    call_key: str=Field(min_length=1,max_length=200)
    target_call_key: str | None=Field(default=None,max_length=200)
    reservation_id: UUID
    command_hash: str=Field(pattern=SHA)
    result_hash: str=Field(pattern=SHA)
    approval_ref: BudgetExactRef
    reservation_ref: BudgetExactRef
    provider_request_ref: BudgetExactRef
    provider_result_id: str=Field(min_length=1,max_length=240)
    signed_certificate: GovernedEvalSignedCertificate
    signed_case: GovernedEvalSignedCase
    issuer_input: GovernedEvalIssuerInput
    certificate_hash: str=Field(pattern=SHA)
    case_envelope_hash: str=Field(pattern=SHA)
    issuer_input_hash: str=Field(pattern=SHA)
    usage_receipt_refs: tuple[BudgetExactRef,...]=Field(min_length=1,max_length=8)
    budget_revision: int=Field(ge=2)
    actual_minor: int=Field(ge=0)
    execution_allowed: Literal[False]=False

    @field_validator('execution_id','case_id','call_key','target_call_key','provider_result_id')
    @classmethod
    def _identity(cls,value):
        if value is not None and value!=value.strip():
            raise ValueError('canonical Route finalization identity required')
        return value

    @model_validator(mode='after')
    def _exact_call(self):
        claim=self.signed_case.claim;certificate=self.signed_certificate.certificate
        usage={(r.resource_type,r.resource_id,r.revision,r.content_hash)
            for r in self.usage_receipt_refs}
        if ((self.purpose=='target' and self.target_call_key is not None)
            or (self.purpose=='judge' and
                (not self.target_call_key or self.target_call_key==self.call_key))
            or self.approval_ref.resource_type!='ActionApprovalEvent'
            or self.reservation_ref.resource_type!='BudgetReservationRevision'
            or self.reservation_ref.resource_id!=str(self.reservation_id)
            or self.provider_request_ref.resource_type!='CapabilityProviderRequestReceipt'
            or len(usage)!=len(self.usage_receipt_refs)
            or any(r.resource_type!='UsageReceipt' for r in self.usage_receipt_refs)
            or (claim.tenant,claim.execution_id,claim.case_id,claim.purpose)
               !=(self.tenant,self.execution_id,self.case_id,self.purpose)
            or claim.subject_kind!='ModelRouteRevision'
            or (certificate.tenant,certificate.execution_id,certificate.case_id,
                certificate.purpose)!=(self.tenant,self.execution_id,self.case_id,self.purpose)
            or self.issuer_input.tenant!=self.tenant
            or (self.issuer_input.issuer_id,self.issuer_input.issuer_key_id)
               !=(certificate.issuer_id,certificate.issuer_key_id)
            or claim.certificate_hash!=self.certificate_hash
            or self.certificate_hash!=_hash(self.signed_certificate)
            or self.case_envelope_hash!=_hash(self.signed_case)
            or self.issuer_input_hash!=_hash(self.issuer_input)):
            raise ValueError('exact Route finalized call proof required')
        return self


class RouteEvalFinalizationProof(AipContractModel):
    schema_version: Literal['aos.route-eval-finalization-proof/v1']='aos.route-eval-finalization-proof/v1'
    tenant: TenantContext
    execution_id: str=Field(min_length=1,max_length=200)
    manifest_hash: str=Field(pattern=SHA)
    context_binding_hash: str=Field(pattern=SHA)
    admission_hash: str=Field(pattern=SHA)
    run_id: str=Field(min_length=1,max_length=200)
    report_id: str=Field(min_length=1,max_length=200)
    report_revision: int=Field(ge=1)
    report_hash: str=Field(pattern=SHA)
    calls: tuple[RouteEvalFinalizedCallProof,...]=Field(min_length=2,max_length=20_000)
    finalized_at: datetime
    execution_allowed: Literal[False]=False

    @field_validator('execution_id','run_id','report_id')
    @classmethod
    def _identity(cls,value):
        if value!=value.strip():raise ValueError('canonical Route finalization identity required')
        return value

    @model_validator(mode='after')
    def _complete_pairs(self):
        if self.finalized_at.utcoffset() is None:
            raise ValueError('timezone-aware Route finalization required')
        keys=[];reservations=set();calls={}
        for item in self.calls:
            key=(item.case_id,item.purpose);keys.append(key)
            if (item.tenant!=self.tenant or item.execution_id!=self.execution_id
                or item.signed_case.claim.manifest_hash!=self.manifest_hash
                or item.signed_case.claim.context_binding_hash!=self.context_binding_hash
                or item.reservation_id in reservations or key in calls
                or item.signed_case.claim.occurred_at>self.finalized_at):
                raise ValueError('Route finalization call set drifted')
            reservations.add(item.reservation_id);calls[key]=item
        cases={case for case,_ in keys}
        expected=[key for case in sorted(cases) for key in ((case,'target'),(case,'judge'))]
        if keys!=expected:
            raise ValueError('ordered complete Target and Judge pairs required')
        for case in cases:
            target=calls[(case,'target')];judge=calls[(case,'judge')]
            claim=judge.signed_case.claim
            if (judge.target_call_key!=target.call_key
                or claim.target_envelope_hash!=target.case_envelope_hash
                or claim.target_output_hash!=target.signed_case.claim.output_hash):
                raise ValueError('exact Target to Judge finalization binding required')
        return self


def canonical_route_eval_finalization_proof(value) -> tuple[str,str]:
    """Revalidate copied objects and return canonical payload/hash."""
    try:
        raw=value.model_dump(mode='json',by_alias=True) if isinstance(
            value,RouteEvalFinalizationProof) else value
        proof=RouteEvalFinalizationProof.model_validate(raw)
        text=json.dumps(proof.model_dump(mode='json',by_alias=True),sort_keys=True,
            separators=(',',':'),ensure_ascii=False,allow_nan=False)
        return text,hashlib.sha256(text.encode()).hexdigest()
    except (ValueError,TypeError,KeyError,AttributeError,json.JSONDecodeError) as exc:
        raise RouteEvalFinalizationConflict('Route finalization proof drifted') from exc


class RouteEvalFinalizationProofStore:
    """Append/read Route sidecars; caller owns transaction and all effects."""

    def __init__(self,*,storage_schema='public',journal=None):
        import re
        if re.fullmatch(r'[a-z_][a-z0-9_]*',storage_schema) is None:
            raise ValueError('invalid Route finalization schema')
        if journal is None:
            from aos_api.aip_model_route_eval_execution_journal import RouteEvalExecutionJournal
            journal=RouteEvalExecutionJournal(storage_schema=storage_schema)
        self.schema=storage_schema;self.journal=journal

    @staticmethod
    def _scope(scope,tenant):
        if (type(scope) is not TenantScope or scope.key!=('org-org','dev-project')
            or (tenant.org_id,tenant.project_id)!=scope.key):
            raise RouteEvalFinalizationConflict('exact Route finalization scope required')

    def _header(self,conn,scope,execution_id):
        return conn.execute(f'''SELECT * FROM {self.schema}.aip_route_eval_finalization_proof
            WHERE org_id=%s AND project_id=%s AND execution_id=%s''',
            (*scope.key,execution_id)).fetchone()

    def _calls(self,conn,scope,execution_id):
        return conn.execute(f'''SELECT * FROM {self.schema}.aip_route_eval_finalized_call_proof
            WHERE org_id=%s AND project_id=%s AND execution_id=%s
            ORDER BY case_id,purpose DESC''',(*scope.key,execution_id)).fetchall()

    def _material(self,conn,scope,execution_id):
        return conn.execute(f'''SELECT * FROM {self.schema}.aip_route_eval_release_material
            WHERE org_id=%s AND project_id=%s AND execution_id=%s''',
            (*scope.key,execution_id)).fetchone()

    def read(self,conn,scope,execution_id):
        if type(scope) is not TenantScope or scope.key!=('org-org','dev-project'):
            raise RouteEvalFinalizationConflict('exact Route finalization scope required')
        header=self._header(conn,scope,execution_id)
        if header is None:return None
        try:
            raw=header['proof_payload'];raw=json.loads(raw) if type(raw) is str else raw
            proof=RouteEvalFinalizationProof.model_validate(raw);text,digest=(
                canonical_route_eval_finalization_proof(proof))
            material=self._material(conn,scope,execution_id)
            rows=self._calls(conn,scope,execution_id)
            indexed={(r['case_id'],r['purpose']):r for r in rows}
            if (len(rows)!=len(proof.calls) or len(indexed)!=len(rows)
                or material is None
                or material['manifest_hash']!=proof.manifest_hash
                or hashlib.sha256(bytes(material['manifest_payload'])).hexdigest()
                   !=proof.manifest_hash
                or digest!=header['proof_hash'] or json.loads(text)!=raw
                or (header['manifest_hash'],header['context_binding_hash'],
                    header['admission_hash'],header['run_id'],header['report_id'],
                    int(header['report_revision']),header['report_hash'],header['finalized_at'])
                   !=(proof.manifest_hash,proof.context_binding_hash,proof.admission_hash,
                      proof.run_id,proof.report_id,proof.report_revision,proof.report_hash,
                      proof.finalized_at)):
                raise ValueError
            for item in proof.calls:
                row=indexed.get((item.case_id,item.purpose));payload=(
                    item.model_dump(mode='json',by_alias=True))
                call_hash=canonical_hash(payload)
                stored=None if row is None else row['call_proof_payload']
                stored=json.loads(stored) if type(stored) is str else stored
                if (row is None or row['reservation_id']!=item.reservation_id
                    or row['call_key']!=item.call_key
                    or row['call_proof_hash']!=call_hash or stored!=payload):
                    raise ValueError
            return proof.model_copy(deep=True)
        except (ValueError,TypeError,KeyError,AttributeError,json.JSONDecodeError):
            raise RouteEvalFinalizationConflict('stored Route finalization drifted') from None

    def persist(self,conn,scope,proof,*,manifest_bytes,presented_cases,
                checked_at,revoked_identity_ids):
        from aos_api.aip_model_route_eval_execution_journal import _canonical
        from aos_api.aip_model_route_eval_owner import (
            PresentedRouteEvalCase,prepare_route_eval_presented_case_bundle,
        )
        try:
            text,digest=canonical_route_eval_finalization_proof(proof)
            value=RouteEvalFinalizationProof.model_validate(json.loads(text))
            self._scope(scope,value.tenant)
            if (type(manifest_bytes) is not bytes
                or not 1<=len(manifest_bytes)<=67_108_864
                or hashlib.sha256(manifest_bytes).hexdigest()!=value.manifest_hash
                or type(presented_cases) is not tuple
                or any(type(x) is not PresentedRouteEvalCase for x in presented_cases)):
                raise ValueError
            prepare_route_eval_presented_case_bundle(manifest_bytes,checked_at=checked_at,
                revoked_identity_ids=revoked_identity_ids,cases=presented_cases)
            presented={(x.envelope.claim.case_id,x.envelope.claim.purpose):x
                for x in presented_cases}
            if len(presented)!=len(presented_cases):raise ValueError
            for item in value.calls:
                witness=presented.get((item.case_id,item.purpose))
                evidence=self.journal.read(conn,scope,item.reservation_id)
                if witness is None or evidence is None or evidence['result'] is None:
                    raise ValueError
                command=evidence['command'];result=evidence['result']
                _,command_hash=_canonical(command);_,result_hash=_canonical(result)
                if (witness.envelope!=item.signed_case
                    or witness.certificate_envelope!=item.signed_certificate
                    or witness.issuer_input!=item.issuer_input
                    or evidence['inputBytes']!=witness.input_bytes
                    or evidence['outputBytes']!=witness.output_bytes
                    or (command.tenant,command.execution_id,command.case_id,command.purpose,
                        command.call_key,command.target_call_key,command.manifest_hash,
                        command.context_binding_hash,command.admission_hash,command_hash,
                        command.budget_request.approval_ref,command.reservation_ref)
                       !=(item.tenant,item.execution_id,item.case_id,item.purpose,
                          item.call_key,item.target_call_key,value.manifest_hash,
                          value.context_binding_hash,value.admission_hash,item.command_hash,
                          item.approval_ref,item.reservation_ref)
                    or (result.provider_request_ref,result.provider_result_id,result_hash)
                       !=(item.provider_request_ref,item.provider_result_id,item.result_hash)):
                    raise ValueError
                row=conn.execute(f'''SELECT state,revision,actual_minor,usage_receipt_refs,
                    provider_request_receipt_ref FROM {self.schema}.aip_budget_reservation
                    WHERE org_id=%s AND project_id=%s AND reservation_id=%s''',
                    (*scope.key,item.reservation_id)).fetchone()
                refs=[exact_ref_payload(r) for r in item.usage_receipt_refs]
                if (row is None or row['state']!='settled'
                    or int(row['revision'])!=item.budget_revision
                    or int(row['actual_minor'])!=item.actual_minor
                    or row['usage_receipt_refs']!=refs
                    or row['provider_request_receipt_ref']!=exact_ref_payload(
                        item.provider_request_ref)):
                    raise ValueError
            current=conn.execute(f'''SELECT r.status,p.content_hash
                FROM {self.schema}.aip_eval_run r
                JOIN {self.schema}.aip_eval_report_revision p
                  ON p.org_id=r.org_id AND p.project_id=r.project_id AND p.run_id=r.run_id
                WHERE r.org_id=%s AND r.project_id=%s AND r.run_id=%s
                  AND p.report_id=%s AND p.revision=%s''',
                (*scope.key,value.run_id,value.report_id,value.report_revision)).fetchone()
            if current is None or current['status']!='succeeded' or current['content_hash']!=value.report_hash:
                raise ValueError
            existing=self._header(conn,scope,value.execution_id)
            if existing is not None:
                original=self.read(conn,scope,value.execution_id)
                material=self._material(conn,scope,value.execution_id)
                if (original!=value or material is None
                    or material['manifest_hash']!=value.manifest_hash
                    or bytes(material['manifest_payload'])!=manifest_bytes):
                    raise ValueError
                return original
            conn.execute(f'''INSERT INTO {self.schema}.aip_route_eval_finalization_proof(
                org_id,project_id,execution_id,proof_hash,proof_payload,manifest_hash,
                context_binding_hash,admission_hash,run_id,report_id,report_revision,
                report_hash,finalized_at) VALUES(%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (*scope.key,value.execution_id,digest,text,value.manifest_hash,
                 value.context_binding_hash,value.admission_hash,value.run_id,value.report_id,
                 value.report_revision,value.report_hash,value.finalized_at))
            conn.execute(f'''INSERT INTO {self.schema}.aip_route_eval_release_material(
                org_id,project_id,execution_id,manifest_hash,manifest_payload)
                VALUES(%s,%s,%s,%s,%s)''',
                (*scope.key,value.execution_id,value.manifest_hash,manifest_bytes))
            for item in value.calls:
                payload=item.model_dump(mode='json',by_alias=True)
                body=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False,
                    allow_nan=False)
                conn.execute(f'''INSERT INTO {self.schema}.aip_route_eval_finalized_call_proof(
                    org_id,project_id,execution_id,case_id,purpose,reservation_id,call_key,
                    call_proof_hash,call_proof_payload) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)''',
                    (*scope.key,value.execution_id,item.case_id,item.purpose,
                     item.reservation_id,item.call_key,canonical_hash(payload),body))
            return value.model_copy(deep=True)
        except RouteEvalFinalizationConflict:
            raise
        except (ValueError,TypeError,KeyError,AttributeError,json.JSONDecodeError):
            raise RouteEvalFinalizationConflict(
                'exact settled Route finalization evidence required') from None
