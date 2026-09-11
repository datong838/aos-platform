"""Current human responsibility checks; not a stage artifact or execution grant."""
from aos_api.aip_assignee_resolution_store import assert_publisher_bundle_version_locked
from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash
from aos_api.aip_production_contracts import CreateResponsibilityPlanRequest
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope

_STAGES = frozenset({'portrait', 'diagnosis', 'solution-design'})


def read_stage_review_responsibility_authority(transaction, scope, *, responsibility_plan_ref, stage, actor):
    if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
        raise TypeError('review authority requires HostTransaction and TenantScope')
    ref = AnalystExactRef.model_validate(responsibility_plan_ref.model_dump())
    if (ref.resource_type != 'ResponsibilityPlanRevision' or stage not in _STAGES
        or type(actor) is not str or not actor or actor.strip() != actor):
        raise ValueError('exact stage reviewer identity required')
    row = transaction.execute('''SELECT revision.*, head.current_revision, head.version
        FROM aip_responsibility_plan_head head JOIN aip_responsibility_plan_revision revision
          ON revision.org_id=head.org_id AND revision.project_id=head.project_id
         AND revision.plan_id=head.plan_id AND revision.revision=head.current_revision
        WHERE head.org_id=%s AND head.project_id=%s AND head.plan_id=%s
        FOR SHARE OF head,revision''', (*scope.key, ref.resource_id)).fetchone()
    if row is None:
        raise ValueError('current responsibility plan unavailable')
    store = AipProductionContractStore(TransactionBoundConnectFactory(transaction, scope))
    plan = store.get_responsibility_plan(scope, ref.resource_id, ref.revision, conn=transaction)
    fields = CreateResponsibilityPlanRequest.model_fields
    typed = plan.model_dump(mode='json', by_alias=True, include=set(fields))
    raw = {field.alias or key: row[key] for key, field in fields.items()}
    if (row['current_revision'] != ref.revision or row['version'] != plan.version
        or plan.revision != ref.revision or plan.content_hash != ref.content_hash
        or canonical_hash(raw) != ref.content_hash or canonical_hash(typed) != ref.content_hash
        or plan.lifecycle != 'frozen' or plan.readiness != 'ready' or plan.coverage != 'complete'
        or plan.blockers or plan.uncovered_slots):
        raise ValueError('responsibility plan is stale, drifted or unavailable')
    slots = [slot for slot in plan.slots if slot.slot_id == f'analyst.{stage}.review']
    if len(slots) != 1:
        raise ValueError('one explicit stage review slot required')
    slot = slots[0]
    if (slot.responsibility_type != 'independent_review' or slot.return_stage != stage
        or slot.assignee.kind != 'human_principal' or slot.assignee.version != 1
        or slot.assignee.resource_id != actor or slot.required_capability_ids
        or not slot.assignee_resolution_receipt_id):
        raise ValueError('actor does not hold the human stage review responsibility')
    member = transaction.execute('''SELECT subject FROM meta_membership
        WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE''', (*scope.key, actor)).fetchone()
    if member is None:
        raise ValueError('stage reviewer is no longer a tenant member')
    receipt = transaction.execute('''SELECT * FROM aip_assignee_resolution_receipt
        WHERE org_id=%s AND project_id=%s AND receipt_id=%s FOR SHARE''',
        (*scope.key, slot.assignee_resolution_receipt_id)).fetchone()
    now = transaction.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    if receipt is None or not receipt['created_at'] <= now < receipt['expires_at']:
        raise ValueError('stage reviewer resolution is not current')
    snapshot = dict(subjectId=receipt['subject_id'], requiredCapabilities=receipt['required_capability_refs'],
        candidates=receipt['candidate_decisions'], selectedAssignee=receipt['selected_assignee'],
        policyRefs=receipt['policy_refs'], bundleVersionLock=assert_publisher_bundle_version_locked())
    payload = dict(snapshot, kind=receipt['kind'], resourceId=receipt['resource_id'], version=receipt['version'],
        status=receipt['status'], resolvedRef=receipt['resolved_ref'], blockerCodes=receipt['blocker_codes'],
        bindingRefs=receipt['binding_refs'], snapshotHash=receipt['snapshot_hash'])
    if canonical_hash(snapshot) != receipt['snapshot_hash'] or canonical_hash(payload) != receipt['content_hash']:
        raise ValueError('stage reviewer resolution body drifted')
    # Re-check after acquiring the receipt lock; the Owner validates exact selection and capability coverage.
    store._require_exact_assignee_resolution(transaction, scope, slot.assignee_resolution_receipt_id,
        slot.assignee, set(), slot.slot_id)
    slot_body=slot.model_dump(mode='json',by_alias=True)
    validation=dict(kind='validate_review_slot',stage=stage,actor=actor,
        slotId=slot.slot_id,responsibilityType=slot.responsibility_type,
        requiredCapabilityIds=slot.required_capability_ids,returnStage=slot.return_stage,
        assignee=slot_body['assignee'],assigneeResolutionReceiptId=slot.assignee_resolution_receipt_id)
    authority_snapshot=dict(schemaVersion='aos.stage-review-responsibility-snapshot/v1',
        responsibilityPlanRef=ref.model_dump(mode='json',by_alias=True),planVersion=plan.version,
        slotId=slot.slot_id,slotHash=canonical_hash(slot_body),memberSubject=member['subject'],
        resolutionReceiptId=slot.assignee_resolution_receipt_id,
        resolutionSnapshotHash=receipt['snapshot_hash'],resolutionContentHash=receipt['content_hash'],
        resolutionCreatedAt=receipt['created_at'].isoformat(),resolutionExpiresAt=receipt['expires_at'].isoformat())
    return dict(reviewer=slot.assignee,snapshot=authority_snapshot,payload=validation,
        expected={'assignee':slot_body['assignee']})


def require_stage_review_authority(transaction,scope,**values):
    return read_stage_review_responsibility_authority(transaction,scope,**values)['reviewer']


__all__=['read_stage_review_responsibility_authority','require_stage_review_authority']
