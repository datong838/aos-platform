"""Pure package-owned Case/Run display projection; no I/O or execution grant."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
import re

from .ecommerce_business_investigation_case import AnalysisType, CaseLifecycle


def _text(value):
    if type(value) is not str or not value or value != value.strip() or not value.isprintable():
        raise ValueError('invalid workspace text')
    return value


def _positive(value):
    if type(value) is not int or value < 1:
        raise ValueError('invalid workspace revision')
    return value


def _record(value, *, schema, tenant):
    if type(value) is not dict or value.get('schemaVersion') != schema or value.get('tenant') != tenant:
        raise ValueError('workspace source scope or schema differs')
    body = {key:child for key,child in value.items() if key != 'contentHash'}
    digest = 'sha256:' + sha256(json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    if value.get('contentHash') != digest:
        raise ValueError('workspace source hash differs')
    _positive(value.get('version'))
    return value


def _ref(record, kind, identity, revision):
    return dict(resourceType=kind,resourceId=_text(record[identity]),revision=_positive(record[revision]),contentHash=record['contentHash'])


def project_workspace(snapshot):
    if type(snapshot) is not dict or set(snapshot) != {'schemaVersion','tenant','cutoffAt','cases','truncated'}:
        raise ValueError('invalid workspace snapshot')
    tenant = snapshot['tenant']
    if snapshot['schemaVersion'] != 'aos.analyst-workspace-snapshot/v1' or type(tenant) is not dict or set(tenant) != {'orgId','projectId'}:
        raise ValueError('invalid workspace snapshot scope')
    for value in tenant.values():_text(value)
    cutoff = _text(snapshot['cutoffAt'])
    if datetime.fromisoformat(cutoff.replace('Z','+00:00')).utcoffset() is None:
        raise ValueError('workspace cutoff must include timezone')
    if type(snapshot['truncated']) is not bool or type(snapshot['cases']) is not list or len(snapshot['cases']) > 50:
        raise ValueError('workspace snapshot bounds differ')
    if len(json.dumps(snapshot,ensure_ascii=False,allow_nan=False).encode()) > 900_000:
        raise ValueError('workspace snapshot is too large')
    case_ids, run_ids = set(), set()
    items=[]
    for group in snapshot['cases']:
        if type(group) is not dict or set(group) != {'case','runs'} or type(group['runs']) is not list or len(group['runs']) > 10:
            raise ValueError('invalid case workspace group')
        case=_record(group['case'],schema='aos.ecommerce.business-investigation-case/v1',tenant=tenant)
        case_id=_text(case.get('caseId'))
        if case_id in case_ids or case.get('revision') != case['version']:
            raise ValueError('duplicate or inconsistent Case')
        case_ids.add(case_id)
        lifecycle=CaseLifecycle(case.get('lifecycle')).value
        analysis_type=AnalysisType(case.get('analysisType')).value
        runs=[]
        for row in group['runs']:
            if type(row) is not dict or set(row) != {'authority','state'}:
                raise ValueError('invalid Run sources')
            run=_record(row['authority'],schema='aos.ecommerce.business-investigation-run/v1',tenant=tenant)
            state=_record(row['state'],schema='aos.ecommerce.business-investigation-run-state/v1',tenant=tenant)
            run_id=_text(run.get('runId'))
            case_ref=run.get('caseRef')
            if (run_id in run_ids or state.get('runId') != run_id or run['version'] != 1
                    or type(case_ref) is not dict or case_ref.get('resourceType') != 'BusinessInvestigationCaseRevision'
                    or set(case_ref) - {'resourceType','resourceId','revision','contentHash','receiptId'}
                    or case_ref.get('resourceId') != case_id or state.get('eventSequence') != state['version']
                    or state.get('lifecycle') not in {'PREPARING','WAITING_DATA'}
                    or state.get('control') not in {'RUNNING','PAUSED','UNKNOWN','RECONCILING','CANCELLED'}):
                raise ValueError('Run source linkage or state differs')
            ref_revision = _positive(case_ref.get('revision'))
            if (ref_revision > case['revision'] or type(case_ref.get('contentHash')) is not str
                    or not re.fullmatch(r'sha256:[0-9a-f]{64}',case_ref['contentHash'])
                    or (ref_revision == case['revision'] and case_ref['contentHash'] != case['contentHash'])):
                raise ValueError('Run Case reference differs')
            if case_ref.get('receiptId') is not None:
                _text(case_ref['receiptId'])
            run_ids.add(run_id)
            runs.append(dict(runRef=_ref(run,'BusinessInvestigationRun','runId','version'),
                stateRef=_ref(state,'BusinessInvestigationRunStateRevision','runId','version'),
                caseRef=deepcopy(case_ref),lifecycle=state['lifecycle'],control=state['control']))
        items.append(dict(caseRef=_ref(case,'BusinessInvestigationCaseRevision','caseId','revision'),
                          title=_text(case.get('title')),analysisType=analysis_type,lifecycle=lifecycle,runs=runs))
    return dict(schemaVersion='aos.analyst-workspace-view/v1',tenant=deepcopy(tenant),cutoffAt=cutoff,
                cases=items,caseCount=len(items),runCount=len(run_ids),truncated=snapshot['truncated'],executionAllowed=False)
