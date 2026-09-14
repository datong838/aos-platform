"""Compose current installed facts under original owners, without a resume grant."""
from psycopg import sql

from aos_api.ecommerce_analysis_query_binding import AnalysisQueryBinding
from aos_api.ecommerce_analysis_snapshot_business_evidence import AnalysisSnapshotBusinessEvidence
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_readiness_policy import compile_snapshot_readiness_policy
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES, ExactResourceRef
from aos_api.source_readiness_snapshot_contracts import InstalledSnapshotReadinessInput


def _ref(value):
    value = PipelineExactRef.model_validate(value)
    return ExactResourceRef(resource_type=value.resource_type, resource_id=value.resource_id,
        revision=str(value.revision), content_hash=value.content_hash.removeprefix("sha256:"),
        authority="installed:original-pipeline-control")


def _members(original):
    result = {draft.pipeline_id: (draft, mapping, parent)
        for (_, draft, mapping), parent in zip(original.group.members, original.parents)}
    expected = {s.pipeline_id: s.object_type for s in CANONICAL_QYH_SOURCES}
    if (len(original.group.members) != 12 or len(original.parents) != 12 or len(result) != 12
            or {key: mapping.read_spec.object_type for key, (_, mapping, _) in result.items()} != expected):
        raise ValueError("readiness requires the complete canonical P01-P12 group")
    return result


def _assemble(*, scope, original, counts, runs, quality, business, field_ref,
              policy_ref, binding, checked_at):
    members = _members(original)
    if counts['tenant'] != dict(orgId=scope.org_id, projectId=scope.project_id):
        raise PermissionError('base counts tenant differs')
    indexed = {m['pipelineId']: m for m in counts['members']}
    if len(counts['members']) != 12 or set(indexed) != set(members) or set(runs) != set(members):
        raise ValueError('complete original base counts and runs required')
    expiry = min(quality.assessment.freshness_expires_at, original.group.expires_at, binding.expires_at)
    field = _ref(field_ref)
    policy = _ref(policy_ref)
    reasons = quality.assessment.reasons
    sources = []
    for canonical in CANONICAL_QYH_SOURCES:
        draft, mapping, parent = members[canonical.pipeline_id]
        count = indexed[canonical.pipeline_id]
        run = runs[canonical.pipeline_id]
        if (count['runId'] != parent['runId'] or run['run_id'] != parent['runId']
                or count['objectType'] != canonical.object_type):
            raise ValueError('current count or run identity differs')
        failures = [r for r in reasons if ':' not in r or r.endswith(':' + canonical.object_type)]
        if canonical.object_type not in business['factIds'] and not failures:
            failures.append('FACT_NOT_COVERED:' + canonical.object_type)
        sources.append(dict(tenant=dict(orgId=scope.org_id, projectId=scope.project_id),
            source_id=draft.source_id, pipeline_id=draft.pipeline_id, object_type=canonical.object_type,
            observed_at=original.read_started_at, freshness_expires_at=expiry,
            source_config_ref=_ref(draft.source_configuration_ref), mapping_ref=_ref(draft.mapping_ref),
            schema_ref=_ref(draft.schema_ref), masking_policy_ref=_ref(draft.masking_policy_ref),
            freshness_policy_ref=policy, reconciliation_policy_ref=policy, quality_policy_ref=field,
            query_capability_ref=binding.binding_ref, latest_run=run,
            counts=dict(source_total=count['sourceTotal'], source_active=count['sourceActive'],
                source_deleted=count['sourceDeleted'], projection_total=count['projectedBaseTotal'],
                unexplained_delta=count['projectedBaseTotal']-count['sourceTotal']),
            quality=dict(status='fail' if failures else 'pass', rule_ref=field,
                summary=';'.join(failures) if failures else 'original current per-fact quality passed')))
    return InstalledSnapshotReadinessInput(tenant=dict(orgId=scope.org_id, projectId=scope.project_id),
        checked_at=checked_at, cutoff_at=original.read_completed_at, sources=sources)


class AnalysisSnapshotReadinessContext:
    def __init__(self, business):
        if type(business) is not AnalysisSnapshotBusinessEvidence:
            raise TypeError('original business evidence Owner required')
        self.business = business
        self.source = business.source
        self.scope = business.scope
        self.binding = AnalysisQueryBinding(self.scope)

    def _runs(self, conn, original):
        result = {}
        for pipeline, (_, _, parent) in _members(original).items():
            row = conn.execute(sql.SQL('SELECT id,status,finished_at FROM {} WHERE org_id=%s AND project_id=%s AND id=%s').format(
                sql.Identifier(self.source._schema, 'meta_schedule_run')),
                (*self.scope.key, parent['runId'])).fetchone()
            if row is None:
                raise ValueError('original source run unavailable')
            result[pipeline] = dict(run_id=str(row['id']), status=row['status'], finished_at=row['finished_at'])
        return result

    def run_current(self, conn, *, business_ref, policy_ref, execute):
        if not callable(execute):
            raise TypeError('synchronous readiness consumer required')
        def consume_business(business, body, snapshot, quality):
            original = snapshot.quality.assessment.input
            _members(original)
            policy = PipelineExactRef.model_validate(policy_ref)
            tx = HostTransaction(conn)
            fields_owner = self.source._fields
            policies = fields_owner._business._snapshot._quality._assessments._policies
            def load_policy():
                _, relationship_quality, _, fields = fields_owner._load_policies(conn, snapshot,
                    cohort_ref=body['selection']['cohortPolicyRef'], field_ref=body['selection']['fieldPolicyRef'])
                document = policies._load_exported_document(conn, self.scope, original.group, policy,
                    resource_type='SnapshotReadinessPolicy')
                return compile_snapshot_readiness_policy(document, field_policy=fields, quality_policy=relationship_quality)
            compiled = load_policy()
            bindings = tuple((ref, parent['runId']) for (ref, _, _), parent in zip(original.group.members, original.parents))
            def consume_counts(current):
                if (current.projection.payload != body['projection']
                        or current.projection.input.manifest_hash != original.manifest_hash):
                    raise ValueError('base count projection differs from exact source evidence')
                def consume_binding(binding):
                    runs = self._runs(conn, original)
                    checked = tx.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                    value = _assemble(scope=self.scope, original=original, counts=current.payload, runs=runs,
                        quality=quality, business=business, field_ref=body['selection']['fieldPolicyRef'],
                        policy_ref=policy, binding=binding, checked_at=checked)
                    before = value.model_dump(mode='json')
                    result = execute(value)
                    _reject_deferred(result)
                    now = tx.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                    if (value.model_dump(mode='json') != before or self._runs(conn, original) != runs
                            or load_policy() != compiled or any(now >= s.freshness_expires_at for s in value.sources)):
                        raise ValueError('current readiness dependencies changed during consumption')
                    return result
                return self.binding.run_current(conn, binding_id=compiled.query_binding_id, execute=consume_binding)
            return self.source._projections.run_current_base_counts(conn, scope=self.scope,
                group_id=original.claim.group_id, actor=self.source.analysis.source.actor,
                bindings=bindings, execute=consume_counts)
        return self.business._run_current_context(conn, reference=business_ref, execute=consume_business)
