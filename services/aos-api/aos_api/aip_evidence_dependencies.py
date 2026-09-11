"""Availability checks for explicitly declared, same-tenant leaf Evidence."""
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.data_requirement_store import canonical_hash

POLICY = 'aos.evidence-dependencies/v1'


def require_evidence_dependencies(conn, scope, payload):
    refs = payload.get('upstreamEvidenceRefs')
    if payload.get('evidencePolicyVersion') != POLICY or type(refs) is not list or not 1 <= len(refs) <= 100:
        raise ValueError('invalid evidence dependency policy')
    seen = set()
    for raw in refs:
        if type(raw) is not dict or type(raw.get('revision')) is not int:
            raise ValueError('strict evidence dependency reference required')
        ref = ExactRevisionRef.model_validate(raw)
        if ref.resource_type != 'Evidence' or ref.revision != 1 or ref.resource_id in seen:
            raise ValueError('invalid evidence dependency identity')
        seen.add(ref.resource_id)
        row = conn.execute('''SELECT e.content_hash,e.payload,EXISTS(
            SELECT 1 FROM aip_evidence_revoke_event r WHERE r.org_id=e.org_id
            AND r.project_id=e.project_id AND r.evidence_id=e.evidence_id
            AND r.revision=1 AND r.content_hash=e.content_hash) AS revoked
            FROM aip_evidence e WHERE org_id=%s AND project_id=%s AND evidence_id=%s''',
            (*scope.key, ref.resource_id)).fetchone()
        if (row is None or row['revoked'] or row['content_hash'] != ref.content_hash
            or type(row['payload']) is not dict or canonical_hash(row['payload']) != ref.content_hash
            or 'evidencePolicyVersion' in row['payload']):
            raise ValueError('evidence dependency unavailable')
