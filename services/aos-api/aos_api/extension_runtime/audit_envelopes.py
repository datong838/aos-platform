"""Immutable generic audit data; no domain code or executable rendering."""
import json
import re
from typing import Literal
from uuid import UUID,NAMESPACE_URL,uuid5

from pydantic import BaseModel,ConfigDict,Field,AwareDatetime,field_validator,model_validator
from psycopg.types.json import Jsonb
from .lifecycle_store import _require_transaction,_values,_digest,RuntimeConflict


class _Immutable(BaseModel):
    model_config=ConfigDict(strict=True,extra="forbid",frozen=True)


class ExactRef(_Immutable):
    authority:str=Field(min_length=1,max_length=160,pattern=r"^[a-z][a-z0-9_.-]*$")
    id:str=Field(min_length=1,max_length=240)
    revision:int=Field(ge=1)
    hash:str=Field(pattern=r"^sha256:[0-9a-f]{64}$")


class AuditArtifact(_Immutable):
    ref:ExactRef
    media_type:str=Field(min_length=3,max_length=160,pattern=r"^[a-zA-Z0-9.+-]+/[a-zA-Z0-9.+-]+$")
    size:int=Field(ge=0,le=2**53-1)


class AuditEnvelope(_Immutable):
    schema_version:Literal[1]=1
    installation_id:UUID
    business_title:str=Field(min_length=1,max_length=240)
    summary:str=Field(min_length=1,max_length=8192)
    actor:str=Field(min_length=1,max_length=240)
    occurred_at:AwareDatetime
    source_ref:ExactRef
    schema_ref:ExactRef
    retention_policy_ref:ExactRef
    task_refs:tuple[ExactRef,...]=Field(default=(),max_length=64)
    run_refs:tuple[ExactRef,...]=Field(default=(),max_length=64)
    approval_refs:tuple[ExactRef,...]=Field(default=(),max_length=64)
    cost_refs:tuple[ExactRef,...]=Field(default=(),max_length=64)
    artifacts:tuple[AuditArtifact,...]=Field(default=(),max_length=64)

    @field_validator("schema_version",mode="before")
    @classmethod
    def exact_version(cls,value):
        if type(value) is not int:
            raise ValueError("integer schema version required")
        return value

    @field_validator("business_title")
    @classmethod
    def business_language(cls,value):
        if not re.search(r"[\u4e00-\u9fff]",value):
            raise ValueError("Chinese business title required")
        return value

    @field_validator("business_title","summary","actor")
    @classmethod
    def plain_text(cls,value):
        if not value.strip() or any(ord(c)<32 and c not in "\n\t" for c in value):
            raise ValueError("invalid plain text")
        return value

    @model_validator(mode="after")
    def bounded(self):
        if len(self.model_dump_json().encode("utf-8"))>65536:
            raise ValueError("audit envelope exceeds 64KiB")
        return self


def _scope(conn,org_id,project_id):
    _require_transaction(conn)
    row=conn.execute("SELECT current_setting('aos.org_id',true) AS org_id,current_setting('aos.project_id',true) AS project_id").fetchone()
    if not org_id or not project_id or _values(row,("org_id","project_id"))!=(org_id,project_id):
        raise PermissionError("audit tenant scope mismatch")


def _authorize(conn,ref,authorize):
    if not callable(authorize) or authorize(conn,ref) is not True:
        raise PermissionError("current source access required")


def _authorize_envelope(conn,envelope,authorize):
    refs=(envelope.source_ref,envelope.schema_ref,envelope.retention_policy_ref,
          *envelope.task_refs,*envelope.run_refs,*envelope.approval_refs,*envelope.cost_refs,
          *(artifact.ref for artifact in envelope.artifacts))
    for ref in dict.fromkeys(refs):
        _authorize(conn,ref,authorize)


def append_envelope(conn,*,org_id,project_id,envelope,authorize):
    _scope(conn,org_id,project_id)
    if not isinstance(envelope,AuditEnvelope):
        raise ValueError("typed audit envelope required")
    # Revalidate model_copy/construct callers; immutable DTO is not authorization.
    envelope=AuditEnvelope.model_validate_json(envelope.model_dump_json())
    _authorize_envelope(conn,envelope,authorize)
    identity=uuid5(NAMESPACE_URL,_digest(["aos.extension.audit.v1",org_id,project_id,envelope.source_ref.model_dump()]))
    payload=envelope.model_dump(mode="json")
    conn.execute("""INSERT INTO extension_audit_envelope
        (org_id,project_id,envelope_id,installation_id,business_title,envelope,source_receipt_ref,occurred_at)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(org_id,project_id,envelope_id) DO NOTHING""",
        (org_id,project_id,identity,envelope.installation_id,envelope.business_title,Jsonb(payload),
         Jsonb(envelope.source_ref.model_dump()),envelope.occurred_at))
    row=conn.execute("SELECT envelope FROM extension_audit_envelope WHERE org_id=%s AND project_id=%s AND envelope_id=%s",
        (org_id,project_id,identity)).fetchone()
    if row is None or _values(row,("envelope",))[0]!=payload:
        raise RuntimeConflict("source receipt already has a different audit projection")
    return identity


def read_envelope(conn,*,org_id,project_id,envelope_id,authorize):
    _scope(conn,org_id,project_id)
    row=conn.execute("""SELECT envelope,source_receipt_ref FROM extension_audit_envelope
        WHERE org_id=%s AND project_id=%s AND envelope_id=%s""",(org_id,project_id,UUID(str(envelope_id)))).fetchone()
    if row is None:
        raise LookupError("audit envelope not found")
    payload,source=_values(row,("envelope","source_receipt_ref"))
    ref=ExactRef.model_validate(source)
    _authorize(conn,ref,authorize)
    result=AuditEnvelope.model_validate_json(json.dumps(payload,ensure_ascii=False))
    if result.source_ref!=ref:
        raise RuntimeConflict("audit source reference mismatch")
    _authorize_envelope(conn,result,authorize)
    return result
