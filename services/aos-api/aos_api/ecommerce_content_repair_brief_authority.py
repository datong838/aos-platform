"""Read an exact public Brief revision made for one human RETURN.

This read-only proof does not authorize a budget hold or Provider invocation.
"""

from __future__ import annotations

from typing import Any, Mapping

from aos_api.aip_production_contract_store import canonical_hash
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.tenant_scope import TenantScope


def _exact(value: Mapping[str, Any], kind: str) -> InvestigationExactRef:
    if type(value) is not dict or set(value) != {
        "resourceType", "resourceId", "revision", "contentHash"
    }:
        raise ValueError("repair Brief exact ref shape drifted")
    ref = InvestigationExactRef.model_validate(value)
    if (ref.resource_type != kind or type(ref.revision) is not int
            or ref.model_dump(mode="json", by_alias=True, exclude_none=True) != value):
        raise ValueError("repair Brief exact ref drifted")
    return ref


def require_repair_brief(
    transaction: Any, scope: TenantScope, brief_ref: Mapping[str, Any],
    prior_brief_ref: Mapping[str, Any], return_decision_ref: Mapping[str, Any],
    prior_artifact_ref: Mapping[str, Any], *, task_id: str, reason: str,
    _expected_head_revision: int | None = None,
) -> None:
    """Verify the current revision and public revise Receipt in one scoped snapshot."""
    if (type(scope) is not TenantScope or type(task_id) is not str or not task_id
            or type(reason) is not str or not reason.strip() or reason != reason.strip()):
        raise ValueError("scoped repair Brief authority required")
    current = _exact(brief_ref, "TaskBriefRevision")
    prior = _exact(prior_brief_ref, "TaskBriefRevision")
    decision = _exact(return_decision_ref, "ReturnDecision")
    if (current.resource_id != prior.resource_id or current.revision != prior.revision + 1
            or decision.revision != 1 or current.revision < 2):
        raise ValueError("repair Brief must directly revise the reviewed revision")
    head_revision = (current.revision if _expected_head_revision is None
                     else _expected_head_revision)
    if type(head_revision) is not int or head_revision not in (
        current.revision, current.revision + 1,
    ):
        raise ValueError("repair Brief active head revision drifted")
    if (type(prior_artifact_ref) is not dict or set(prior_artifact_ref) != {
            "resourceType", "resourceId", "contentHash"}
            or prior_artifact_ref["resourceType"] != "Artifact"
            or type(prior_artifact_ref["resourceId"]) is not str
            or not prior_artifact_ref["resourceId"]
            or type(prior_artifact_ref["contentHash"]) is not str
            or len(prior_artifact_ref["contentHash"]) != 64):
        raise ValueError("repair Brief prior Artifact ref drifted")
    rows = transaction.execute(
        """SELECT head.task_id,head.current_revision,head.version,
                  current.brief_type,current.schema_ref,current.spec,current.content_hash,
                  current.lifecycle,current.created_by,
                  previous.brief_type AS previous_brief_type,
                  previous.schema_ref AS previous_schema_ref,
                  previous.spec AS previous_spec,
                  previous.content_hash AS previous_content_hash,
                  receipt.request_hash AS receipt_request_hash,
                  receipt.result_ref AS receipt_result_ref,
                  receipt.created_by AS receipt_created_by
             FROM public.aip_task_brief_head head
             JOIN public.aip_task_brief_revision current
               ON current.org_id=head.org_id AND current.project_id=head.project_id
              AND current.brief_id=head.brief_id AND current.revision=%s
             JOIN public.aip_task_brief_revision previous
               ON previous.org_id=head.org_id AND previous.project_id=head.project_id
              AND previous.brief_id=head.brief_id AND previous.revision=%s-1
             JOIN public.aip_production_contract_receipt receipt
               ON receipt.org_id=head.org_id AND receipt.project_id=head.project_id
              AND receipt.operation='task_brief.revise'
              AND receipt.result_ref->>'resourceId'=head.brief_id
              AND receipt.result_ref->>'revision'=%s::text
            WHERE head.org_id=%s AND head.project_id=%s AND head.brief_id=%s
            LIMIT 2""",
        (current.revision, current.revision, current.revision,
         *scope.key, current.resource_id),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("unique public repair Brief revision/Receipt missing")
    row = dict(rows[0])
    prior_spec, spec = row.get("previous_spec"), row.get("spec")
    if type(prior_spec) is not dict or type(spec) is not dict:
        raise ValueError("repair Brief specs unavailable")
    expected_repair = {
        "returnDecisionRef": dict(return_decision_ref),
        "priorArtifactRef": dict(prior_artifact_ref),
        "humanReason": reason,
    }
    expected_spec = {**prior_spec, "repair": expected_repair}
    expected_hash = canonical_hash({
        "briefType": row.get("brief_type"), "schemaRef": row.get("schema_ref"),
        "spec": spec,
    })
    expected_request_hash = canonical_hash({
        "briefId": current.resource_id, "expectedVersion": prior.revision,
        "briefType": row.get("brief_type"), "schemaRef": row.get("schema_ref"),
        "spec": spec,
    })
    expected_result_ref = {
        "resourceType": "TaskBriefRevision", "resourceId": current.resource_id,
        "revision": current.revision, "contentHash": expected_hash,
    }
    if (
        row.get("task_id") != task_id
        or row.get("current_revision") != head_revision
        or row.get("version") != head_revision
        or row.get("brief_type") != "content_campaign"
        or row.get("previous_brief_type") != row.get("brief_type")
        or row.get("previous_schema_ref") != row.get("schema_ref")
        or row.get("previous_content_hash") != prior.content_hash.removeprefix("sha256:")
        or row.get("content_hash") != expected_hash
        or current.content_hash != "sha256:" + expected_hash
        or row.get("lifecycle") != "draft"
        or type(row.get("created_by")) is not str or not row["created_by"]
        or row.get("receipt_created_by") != row["created_by"]
        or row.get("receipt_request_hash") != expected_request_hash
        or row.get("receipt_result_ref") != expected_result_ref
        or spec != expected_spec
        or spec.get("externalPublicationRequested") is not False
    ):
        raise ValueError("public repair Brief revision/Receipt drifted")


def require_frozen_repair_brief(
    transaction: Any, scope: TenantScope, frozen_ref: Mapping[str, Any],
    prior_brief_ref: Mapping[str, Any], return_decision_ref: Mapping[str, Any],
    prior_artifact_ref: Mapping[str, Any], *, task_id: str, reason: str,
) -> None:
    """Require public revise then public freeze, with unchanged repair content."""
    frozen = _exact(frozen_ref, "TaskBriefRevision")
    prior = _exact(prior_brief_ref, "TaskBriefRevision")
    if (frozen.resource_id != prior.resource_id
            or frozen.revision != prior.revision + 2):
        raise ValueError("frozen repair Brief must follow the revised draft")
    rows = transaction.execute(
        """SELECT head.task_id,head.current_revision,head.version,
                  frozen.brief_type,frozen.schema_ref,frozen.spec,
                  frozen.content_hash,frozen.lifecycle,frozen.created_by,
                  draft.brief_type AS draft_brief_type,
                  draft.schema_ref AS draft_schema_ref,
                  draft.spec AS draft_spec,draft.content_hash AS draft_content_hash,
                  draft.lifecycle AS draft_lifecycle,
                  receipt.request_hash AS receipt_request_hash,
                  receipt.result_ref AS receipt_result_ref,
                  receipt.created_by AS receipt_created_by
             FROM public.aip_task_brief_head head
             JOIN public.aip_task_brief_revision frozen
               ON frozen.org_id=head.org_id AND frozen.project_id=head.project_id
              AND frozen.brief_id=head.brief_id AND frozen.revision=%s
             JOIN public.aip_task_brief_revision draft
               ON draft.org_id=head.org_id AND draft.project_id=head.project_id
              AND draft.brief_id=head.brief_id AND draft.revision=%s-1
             JOIN public.aip_production_contract_receipt receipt
               ON receipt.org_id=head.org_id AND receipt.project_id=head.project_id
              AND receipt.operation='task_brief.freeze'
              AND receipt.result_ref->>'resourceId'=head.brief_id
              AND receipt.result_ref->>'revision'=%s::text
            WHERE head.org_id=%s AND head.project_id=%s AND head.brief_id=%s
            LIMIT 2""",
        (frozen.revision, frozen.revision, frozen.revision,
         *scope.key, frozen.resource_id),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("unique public frozen repair Brief/Receipt missing")
    row = dict(rows[0])
    draft_ref = {
        "resourceType": "TaskBriefRevision", "resourceId": frozen.resource_id,
        "revision": frozen.revision - 1,
        "contentHash": "sha256:" + str(row.get("draft_content_hash")),
    }
    if (
        row.get("task_id") != task_id
        or row.get("current_revision") != frozen.revision
        or row.get("version") != frozen.revision
        or row.get("brief_type") != "content_campaign"
        or row.get("draft_brief_type") != row.get("brief_type")
        or row.get("draft_schema_ref") != row.get("schema_ref")
        or type(row.get("spec")) is not dict
        or row.get("draft_spec") != row.get("spec")
        or row.get("draft_content_hash") != row.get("content_hash")
        or frozen.content_hash != "sha256:" + str(row.get("content_hash"))
        or row.get("draft_lifecycle") != "draft"
        or row.get("lifecycle") != "frozen"
        or type(row.get("created_by")) is not str or not row["created_by"]
        or row.get("receipt_created_by") != row["created_by"]
        or row.get("receipt_request_hash") != canonical_hash({
            "briefId": frozen.resource_id,
            "expectedVersion": frozen.revision - 1,
        })
        or row.get("receipt_result_ref") != {
            "resourceType": "TaskBriefRevision",
            "resourceId": frozen.resource_id,
            "revision": frozen.revision,
            "contentHash": row.get("content_hash"),
        }
    ):
        raise ValueError("public frozen repair Brief/Receipt drifted")
    require_repair_brief(
        transaction, scope, draft_ref, prior_brief_ref, return_decision_ref,
        prior_artifact_ref, task_id=task_id, reason=reason,
        _expected_head_revision=frozen.revision,
    )


def require_review_repair_brief(transaction, scope, brief_ref, spec, artifact_ref, *, task_id):
    """Read completed repair lineage for review; this grants no new execution."""
    if type(scope) is not TenantScope or type(task_id) is not str or not task_id:
        raise ValueError('scoped completed repair review required')
    repair = spec.get('repair') if type(spec) is dict else None
    if type(repair) is not dict or set(repair) != {'returnDecisionRef', 'priorArtifactRef', 'humanReason'}:
        raise ValueError('frozen review Brief requires exact repair lineage')
    decision = _exact(repair['returnDecisionRef'], 'ReturnDecision')
    artifact = _exact(artifact_ref, 'ArtifactRevision')
    if decision.revision != 1 or artifact.revision != 1:
        raise ValueError('review repair reference revision drifted')
    row = transaction.execute(
        '''SELECT d.*,r.task_id,i.artifact_id,i.artifact_hash,i.status AS issue_status,
                  i.version AS current_issue_version,a.content_hash AS old_artifact_hash,
                  a.metadata AS old_metadata,a.run_id AS old_run_id,
                  n.run_id AS new_run_id,n.content_hash AS new_artifact_hash,
                  s.status AS step_status,s.attempt AS step_attempt
             FROM public.aip_return_decision d
             JOIN public.aip_task_run r ON r.org_id=d.org_id AND r.project_id=d.project_id AND r.run_id=d.run_id
             JOIN public.aip_review_issue i ON i.org_id=d.org_id AND i.project_id=d.project_id AND i.issue_id=d.issue_id
             JOIN public.aip_artifact a ON a.org_id=i.org_id AND a.project_id=i.project_id AND a.artifact_id=i.artifact_id
             JOIN public.aip_artifact n ON n.org_id=d.org_id AND n.project_id=d.project_id AND n.artifact_id=%s
             JOIN public.aip_step_run s ON s.org_id=d.org_id AND s.project_id=d.project_id
              AND s.step_run_id=d.step_run_id AND s.run_id=d.run_id AND s.step_key=d.step_key
            WHERE d.org_id=%s AND d.project_id=%s AND d.decision_id=%s''',
        (artifact.resource_id, *scope.key, decision.resource_id),
    ).fetchone()
    if row is None:
        raise ValueError('completed review repair source missing')
    payload = dict(issueId=row['issue_id'], issueVersion=row['issue_version'], runId=row['run_id'],
        stepKey=row['step_key'], stepRunId=row['step_run_id'], attempt=row['attempt'],
        attemptIdempotencyKey=row['attempt_idempotency_key'], reason=row['reason'], actor=row['actor'])
    prior = dict(resourceType='Artifact', resourceId=row['artifact_id'], contentHash=row['artifact_hash'])
    if (row['task_id'] != task_id or row['decision_hash'] != canonical_hash(payload)
            or decision.content_hash != 'sha256:' + row['decision_hash']
            or repair['priorArtifactRef'] != prior or repair['humanReason'] != row['reason']
            or row['old_artifact_hash'] != row['artifact_hash']
            or row['new_artifact_hash'] != artifact.content_hash.removeprefix('sha256:')
            or row['old_run_id'] != row['run_id'] or row['new_run_id'] != row['run_id']
            or artifact.resource_id == row['artifact_id']
            or row['issue_status'] != 'returned' or row['current_issue_version'] != row['issue_version'] + 1
            or row['step_key'] != 'content_generate' or type(row['attempt']) is not int or row['attempt'] < 2
            or row['step_status'] != 'succeeded' or row['step_attempt'] != row['attempt']):
        raise ValueError('completed review repair lineage drifted')
    metadata = row['old_metadata']
    content = metadata.get('ecommerceGrowthContentArtifact') if type(metadata) is dict else None
    previous = content.get('briefRef') if type(content) is dict else None
    if type(previous) is not dict:
        raise ValueError('review repair previous Brief unavailable')
    require_frozen_repair_brief(transaction, scope, brief_ref, previous,
        repair['returnDecisionRef'], prior, task_id=task_id, reason=row['reason'])


def read_created_brief_origin(transaction, scope, current_ref, *, task_id):
    """Project a publicly revised/frozen Brief onto its unchanged creation source."""
    if type(scope) is not TenantScope or type(task_id) is not str or not task_id:
        raise ValueError('scoped repair Brief origin required')
    current = _exact(current_ref, 'TaskBriefRevision')
    if current.revision < 3 or current.revision % 2 != 1:
        raise ValueError('current frozen repair Brief revision required')
    rows = transaction.execute(
        '''SELECT h.task_id,h.current_revision,h.version,
                  c.task_id AS current_task,c.brief_type AS current_type,c.schema_ref AS current_schema,
                  c.spec AS current_spec,c.content_hash AS current_hash,c.lifecycle AS current_lifecycle,
                  r.task_id AS root_task,r.brief_type AS root_type,r.schema_ref AS root_schema,
                  r.spec AS root_spec,r.content_hash AS root_hash,r.lifecycle AS root_lifecycle,
                  r.created_by AS root_actor,p.created_by AS receipt_actor,
                  p.request_hash AS receipt_hash,p.result_ref AS receipt_result,
                  a.content_hash AS old_artifact_hash,a.metadata AS old_metadata
             FROM public.aip_task_brief_head h
             JOIN public.aip_task_brief_revision c ON c.org_id=h.org_id AND c.project_id=h.project_id
              AND c.brief_id=h.brief_id AND c.revision=h.current_revision
             JOIN public.aip_task_brief_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id
              AND r.brief_id=h.brief_id AND r.revision=1
             JOIN public.aip_production_contract_receipt p ON p.org_id=h.org_id AND p.project_id=h.project_id
              AND p.operation='task_brief.create' AND p.result_ref->>'resourceId'=h.brief_id
             LEFT JOIN public.aip_artifact a ON a.org_id=h.org_id AND a.project_id=h.project_id
              AND a.artifact_id=c.spec->'repair'->'priorArtifactRef'->>'resourceId'
            WHERE h.org_id=%s AND h.project_id=%s AND h.brief_id=%s LIMIT 2''',
        (*scope.key, current.resource_id),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError('unique repair Brief creation source missing')
    row = rows[0]
    root_spec, spec = row['root_spec'], row['current_spec']
    repair = spec.get('repair') if type(spec) is dict else None
    if type(root_spec) is not dict or type(repair) is not dict or set(repair) != {'returnDecisionRef','priorArtifactRef','humanReason'}:
        raise ValueError('repair Brief creation specs unavailable')
    digest = lambda kind, schema, value: canonical_hash(dict(briefType=kind, schemaRef=schema, spec=value))
    root_hash = digest(row['root_type'], row['root_schema'], root_spec)
    current_hash = digest(row['current_type'], row['current_schema'], spec)
    root = dict(resourceType='TaskBriefRevision', resourceId=current.resource_id, revision=1, contentHash='sha256:' + root_hash)
    if (row['task_id'] != task_id or row['current_task'] != task_id or row['root_task'] != task_id
            or row['current_revision'] != current.revision or row['version'] != current.revision
            or row['current_lifecycle'] != 'frozen' or row['root_lifecycle'] != 'draft'
            or row['current_type'] != 'content_campaign' or row['root_type'] != row['current_type']
            or row['current_schema'] != row['root_schema'] or row['root_hash'] != root_hash
            or row['current_hash'] != current_hash or current.content_hash != 'sha256:' + current_hash
            or row['root_actor'] != 'ecommerce-growth-review-host' or row['receipt_actor'] != row['root_actor']
            or row['receipt_result'] != {**root, 'contentHash': root_hash}
            or row['receipt_hash'] != canonical_hash(dict(taskId=task_id, briefType=row['root_type'], schemaRef=row['root_schema'], spec=root_spec))
            or spec != {**root_spec, 'repair': repair} or root_spec.get('externalPublicationRequested') is not False
            or type(repair['priorArtifactRef']) is not dict
            or repair['priorArtifactRef'].get('contentHash') != row['old_artifact_hash']):
        raise ValueError('repair Brief creation source drifted')
    metadata = row['old_metadata']
    content = metadata.get('ecommerceGrowthContentArtifact') if type(metadata) is dict else None
    previous = content.get('briefRef') if type(content) is dict else None
    if type(previous) is not dict:
        raise ValueError('repair Brief previous source missing')
    require_frozen_repair_brief(transaction, scope, current_ref, previous,
        repair['returnDecisionRef'], repair['priorArtifactRef'], task_id=task_id, reason=repair['humanReason'])
    return root
