"""Package event policy values; parsing never registers or enables a schedule."""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import re
from typing import Any, Mapping

from .ecommerce_business_investigation_case import canonical_hash, _ref_payload
from .sdk_ports import ExactRef, TenantRef

SCHEMA = 'aos.ecommerce.product-event-schedule-policy/v1'
KEYS = frozenset(('schemaVersion','tenant','schedulePolicyId','revision','priorRef',
    'caseRef','sourceSelectionRef','methodRef','platform','shopId','objectTypes',
    'effectiveFrom','effectiveUntil','maxSourceAgeSeconds','recoveryWindowSeconds',
    'createdBy','createdAt','contentHash'))
REF_KEYS = frozenset(('resourceType','resourceId','revision','contentHash','receiptId'))


def _require(condition):
    if not condition:
        raise ValueError('PRODUCT_EVENT_POLICY_INVALID')


def _text(value, limit=200):
    _require(type(value) is str and 1 <= len(value) <= limit
             and value.strip()==value and value.isprintable() and value!='*')


def _date(value):
    _require(type(value) is str)
    try:
        parsed=datetime.fromisoformat(value)
        _require(parsed.utcoffset()==timedelta(0))
        _require(parsed.isoformat()==value)
        return parsed.astimezone(UTC)
    except (TypeError, ValueError, OverflowError):
        raise ValueError('PRODUCT_EVENT_POLICY_TIME_INVALID') from None


def _read_ref(value):
    if value is None:return None
    _require(type(value) is dict and set(value)==REF_KEYS)
    return ExactRef(value['resourceType'],value['resourceId'],value['revision'],
                    value['contentHash'],value['receiptId'])


def _ref(ref, kind):
    _require(type(ref) is ExactRef and ref.resource_type==kind and ref.receipt_id is None)
    _text(ref.resource_id,240)


@dataclass(frozen=True, slots=True)
class ProductEventSchedulePolicy:
    tenant: TenantRef
    policy_id: str
    revision: int
    prior_ref: ExactRef | None
    case_ref: ExactRef
    source_selection_ref: ExactRef
    method_ref: ExactRef
    platform: str
    shop_id: str
    object_types: tuple[str, ...]
    effective_from: datetime
    effective_until: datetime
    max_source_age_seconds: int
    recovery_window_seconds: int
    created_by: str
    created_at: datetime
    content_hash: str

    def __post_init__(self):
        _require(type(self.tenant) is TenantRef)
        for value in (self.tenant.org_id,self.tenant.project_id,self.policy_id,self.shop_id,self.created_by):
            _text(value)
        _require(type(self.platform) is str and re.fullmatch(r'[a-z][a-z0-9_.-]{0,63}',self.platform) is not None)
        _require(type(self.revision) is int and 1<=self.revision<2**63)
        _ref(self.case_ref,'BusinessInvestigationCaseRevision')
        _ref(self.source_selection_ref,'SourceSelectionRevision')
        _ref(self.method_ref,'InvestigationProfileRevision')
        if self.revision==1:_require(self.prior_ref is None)
        else:
            _ref(self.prior_ref,'SchedulePolicyRevision')
            _require(self.prior_ref.resource_id==self.policy_id and self.prior_ref.revision==self.revision-1)
        _require(type(self.object_types) is tuple and 1<=len(self.object_types)<=2)
        _require(all(type(v) is str and v in ('Product','ProductSku') for v in self.object_types))
        _require(tuple(sorted(set(self.object_types)))==self.object_types)
        for value in (self.effective_from,self.effective_until,self.created_at):
            _require(type(value) is datetime and value.utcoffset()==timedelta(0))
        _require(self.created_at<=self.effective_from<self.effective_until)
        _require(self.effective_until-self.effective_from<=timedelta(days=1))
        for value in (self.max_source_age_seconds,self.recovery_window_seconds):
            _require(type(value) is int and 1<=value<=86400)
        _require(self.content_hash==canonical_hash(self.authority_payload(include_hash=False)))

    def authority_payload(self, *, include_hash=True):
        result=dict(schemaVersion=SCHEMA,
            tenant=dict(orgId=self.tenant.org_id,projectId=self.tenant.project_id),
            schedulePolicyId=self.policy_id,revision=self.revision,priorRef=_ref_payload(self.prior_ref),
            caseRef=_ref_payload(self.case_ref),sourceSelectionRef=_ref_payload(self.source_selection_ref),
            methodRef=_ref_payload(self.method_ref),platform=self.platform,shopId=self.shop_id,
            objectTypes=list(self.object_types),effectiveFrom=self.effective_from.isoformat(),
            effectiveUntil=self.effective_until.isoformat(),maxSourceAgeSeconds=self.max_source_age_seconds,
            recoveryWindowSeconds=self.recovery_window_seconds,createdBy=self.created_by,
            createdAt=self.created_at.isoformat())
        if include_hash:result['contentHash']=self.content_hash
        return result

    @classmethod
    def from_authority(cls, payload: Mapping[str, Any]):
        _require(type(payload) is dict and set(payload)==KEYS and payload['schemaVersion']==SCHEMA)
        tenant=payload['tenant']
        _require(type(tenant) is dict and set(tenant)=={'orgId','projectId'})
        _text(tenant['orgId']); _text(tenant['projectId'])
        _require(type(payload['objectTypes']) is list)
        return cls(TenantRef(tenant['orgId'],tenant['projectId']),payload['schedulePolicyId'],
            payload['revision'],_read_ref(payload['priorRef']),_read_ref(payload['caseRef']),
            _read_ref(payload['sourceSelectionRef']),_read_ref(payload['methodRef']),
            payload['platform'],payload['shopId'],tuple(payload['objectTypes']),
            _date(payload['effectiveFrom']),_date(payload['effectiveUntil']),
            payload['maxSourceAgeSeconds'],payload['recoveryWindowSeconds'],payload['createdBy'],
            _date(payload['createdAt']),payload['contentHash'])

    def validate_successor(self, previous):
        _require(type(previous) is ProductEventSchedulePolicy)
        _require(self.tenant==previous.tenant and self.policy_id==previous.policy_id
                 and self.case_ref.resource_id==previous.case_ref.resource_id
                 and self.revision==previous.revision+1 and self.prior_ref is not None
                 and self.prior_ref.content_hash==previous.content_hash
                 and self.created_at>=previous.created_at
                 and self.effective_from>=previous.effective_from)
