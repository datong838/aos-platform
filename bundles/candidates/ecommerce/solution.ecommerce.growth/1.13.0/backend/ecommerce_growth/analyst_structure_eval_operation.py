"""Fixed, no-I/O structural evaluation; caller must prove source authority."""
from .analyst_structure_case import structure_case_from_query
from .analyst_structure_eval import evaluate_structure


def evaluate_stage_structure(payload):
    if (type(payload) is not dict
        or set(payload) != {'kind', 'stage', 'query', 'subjectArtifactRef', 'subjectText'}
        or payload['kind'] != 'evaluate_stage_structure'):
        raise ValueError('INVALID_STRUCTURE_MESSAGE')
    case = structure_case_from_query(payload['query'], stage=payload['stage'])
    return evaluate_structure(dict(
        schemaVersion='aos.eval-text-subject-input/v1',
        subjectArtifactRef=payload['subjectArtifactRef'],
        subjectText=payload['subjectText'],
        caseInput=case,
    ))
