"""Fixed structural checks on original text; never data or business authority.

The host must derive and bind case inventories to the actual generation inputs.
Passing means only that this answer fits that inventory, not that it is true.
"""
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .ecommerce_analyst_analysis_proposal import parse_portrait_answer, parse_diagnosis_answer
from .ecommerce_analyst_growth_plan_draft import parse_growth_plan_answer

Identity = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=200, pattern=r"^\S(?:.*\S)?$")]
Digest = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]
Index = Annotated[int, Field(strict=True, ge=0)]
Stage = Literal['portrait', 'diagnosis', 'solution-design']


class _Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class _Subject(_Strict):
    resource_type: Literal['Artifact'] = Field(alias='resourceType')
    resource_id: Identity = Field(alias='resourceId')
    content_hash: Digest = Field(alias='contentHash')


class _Source(_Strict):
    resource_type: Literal['EvidenceBundleRevision', 'Evidence', 'DatasetRevision'] = Field(alias='resourceType')
    resource_id: Identity = Field(alias='resourceId')
    revision: Annotated[int, Field(strict=True, ge=1)]
    content_hash: Digest = Field(alias='contentHash')


class _Case(_Strict):
    schema_version: Literal['aos.analyst-structure-case/v1'] = Field(alias='schemaVersion')
    stage: Stage
    source_refs: list[_Source] = Field(alias='sourceRefs', min_length=1, max_length=100)
    metric_sources: list[Annotated[list[Index], Field(min_length=1, max_length=100)]] = Field(alias='metricSources', max_length=100)


class _Input(_Strict):
    schema_version: Literal['aos.eval-text-subject-input/v1'] = Field(alias='schemaVersion')
    subject_artifact_ref: _Subject = Field(alias='subjectArtifactRef')
    subject_text: str = Field(alias='subjectText')
    case_input: _Case = Field(alias='caseInput')


def _read_input(value):
    try:
        if type(value) is not dict:
            raise ValueError()
        item = _Input.model_validate(value)
        body = item.subject_text.encode('utf-8')
        case = item.case_input
        identities = {(s.resource_type, s.resource_id) for s in case.source_refs}
        if (len(body) > 2097152 or sha256(body).hexdigest() != item.subject_artifact_ref.content_hash
                or len(identities) != len(case.source_refs)
                or bool(case.metric_sources) != (case.stage == 'portrait')):
            raise ValueError()
        for indices in case.metric_sources:
            if len(set(indices)) != len(indices) or any(i >= len(case.source_refs) for i in indices):
                raise ValueError()
        return item
    except ValueError:
        # Never propagate Pydantic's input excerpts or business text to reports.
        raise ValueError('INVALID_STRUCTURE_INPUT') from None


def evaluate_structure(value) -> dict[str, object]:
    item = _read_input(value)
    case = item.case_input
    code = 'STRUCTURE_VALID'
    try:
        if case.stage == 'portrait':
            proposal = parse_portrait_answer(item.subject_text, source_count=len(case.source_refs), metric_count=len(case.metric_sources))
            selected = set(proposal.source_indices)
            if any(not set(case.metric_sources[i]).issubset(selected) for i in proposal.metric_indices):
                code = 'METRIC_SOURCE_NOT_SELECTED'
        elif case.stage == 'diagnosis':
            parse_diagnosis_answer(item.subject_text, source_count=len(case.source_refs))
        else:
            parse_growth_plan_answer(item.subject_text, source_count=len(case.source_refs))
    except ValueError:
        code = 'ANSWER_STRUCTURE_INVALID'
    return dict(schemaVersion='aos.analyst-structure-result/v1', stage=case.stage,
                structurePassed=code == 'STRUCTURE_VALID', detailCode=code)
