"""Derive rule inventory from fixed generation inputs, without I/O or authority.

The host must prove this query matches the completed attempt and current Owners.
Self-consistent hashes are not source permission or an execution receipt.
"""
from hashlib import sha256
import json

from .ecommerce_analyst_growth_plan_draft import _unique_object, _reject_constant
from .analyst_structure_eval import validate_structure_case

_PROTOCOLS = {
    'portrait': ('aos.portrait-proposal/v1', {'protocol','method','metrics','evaluation','sources','cutoffAt'}),
    'diagnosis': ('aos.diagnosis-proposal/v1', {'protocol','insight','sources'}),
    'solution-design': ('aos.growth-plan-proposal/v1', {'protocol','decision','planBudget','taskType','sources'}),
}


def _hash(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _revision_body(value):
    if type(value) is not dict or _hash({k:v for k,v in value.items() if k!='contentHash'}) != value['contentHash']:
        raise ValueError()


def _bundles(sources):
    refs=[]; materials=[]
    for source in sources:
        if type(source) is not dict or set(source)!={'bundleRef','cutoffAt','items'}:
            raise ValueError()
        ref=source['bundleRef']
        if ref['resourceType']!='EvidenceBundleRevision':raise ValueError()
        refs.append(ref)
        items=source['items']
        if type(items) is not list or not 1<=len(items)<=100:raise ValueError()
        seen=set();payloads=[]
        for item in items:
            if type(item) is not dict or set(item)!={'evidenceRef','payload'}:raise ValueError()
            evidence=item['evidenceRef']; payload=item['payload']
            if (set(evidence)!={'resourceType','resourceId','revision','contentHash'}
                or evidence['resourceType']!='Evidence' or type(evidence['revision']) is not int
                or evidence['revision']!=1 or type(evidence['resourceId']) is not str or not evidence['resourceId'].strip()
                or evidence['resourceId'] in seen or type(payload) is not dict
                or evidence['contentHash']!=_hash(payload)):
                raise ValueError()
            seen.add(evidence['resourceId']);payloads.append(payload)
        materials.append(payloads)
    return refs,materials


def structure_case_from_query(query: str, *, stage: str) -> dict:
    try:
        if type(stage) is not str or stage not in _PROTOCOLS or type(query) is not str or len(query)>16000:
            raise ValueError()
        payload=json.loads(query,object_pairs_hook=_unique_object,parse_constant=_reject_constant)
        protocol,keys=_PROTOCOLS[stage]
        if type(payload) is not dict or set(payload)!=keys or payload['protocol']!=protocol:raise ValueError()
        sources=payload['sources']
        if type(sources) is not list or not 1<=len(sources)<=100:raise ValueError()
        mappings=[]
        if stage=='solution-design':
            _revision_body(payload['decision'])
            if sources!=payload['decision']['evidenceRefs']:raise ValueError()
            refs=sources
        else:
            refs,materials=_bundles(sources)
            if stage=='diagnosis':
                _revision_body(payload['insight'])
                if refs!=payload['insight']['evidenceRefs']:raise ValueError()
            else:
                metrics=payload['metrics']
                if type(metrics) is not list or not 1<=len(metrics)<=100:raise ValueError()
                seen=set()
                for metric in metrics:
                    _revision_body(metric)
                    if metric['metricId'] in seen:raise ValueError()
                    seen.add(metric['metricId'])
                    expected=dict(resourceType='MetricDefinitionRevision',resourceId=metric['metricId'],revision=metric['revision'],contentHash=metric['contentHash'])
                    matches=[index for index,items in enumerate(materials) for body in items
                             if body.get('metricDefinitionRef')==expected and type(body.get('queryRequest')) is dict and type(body.get('queryResult')) is dict]
                    if len(matches)!=1:raise ValueError()
                    mappings.append(matches)
        result=dict(schemaVersion='aos.analyst-structure-case/v1',stage=stage,sourceRefs=refs,metricSources=mappings)
        return validate_structure_case(result).model_dump(mode='json',by_alias=True)
    except (ValueError,KeyError,TypeError,RecursionError):
        raise ValueError('INVALID_GENERATION_CONTEXT') from None
