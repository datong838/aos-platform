"""Bounded current present-row residual findings; never infer deletions from absence."""
from dataclasses import dataclass
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.ec_ot_writer import _normalize_rows
from aos_api.ecom_core_models import SyncScope
from aos_api.ecom_consistency_store import _db_time
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_snapshot_group_link_command import PipelineSnapshotGroupLinkCommandJournal
from aos_api.source_read_observation import observed_rows_hash


@dataclass(frozen=True)
class SnapshotGroupRelationshipAudit:
    assessment_hash: str
    command_hash: str
    counts: dict
    cleanup_candidates: tuple
    unresolved_extras: tuple
    content_hash: str


def _payload(result):
    return dict(assessmentHash=result.assessment_hash, commandHash=result.command_hash,
                counts=result.counts, cleanupCandidates=list(result.cleanup_candidates),
                unresolvedExtras=list(result.unresolved_extras))


def _identity(row):
    return (row['link_type'], row['source_object_type'], row['source_external_id'],
            row['target_object_type'], row['target_external_id'])


class PipelineSnapshotGroupRelationshipAudit:
    def __init__(self, *, claims, store):
        self._commands = PipelineSnapshotGroupLinkCommandJournal(claims=claims, store=store)
        self._store = store

    def read_current(self, conn, **args):
        return self.run_current(conn, **args, execute=lambda value: value)

    def run_current(self, conn, *, execute, **args):
        return self._run(conn,execute=execute,completed_read=False,**args)

    def read_completed_current(self, conn, **args):
        return self.run_completed_current(conn,execute=lambda value:value,**args)

    def run_completed_current(self, conn, *, execute, **args):
        return self._run(conn,execute=execute,completed_read=True,**args)

    def _run(self, conn, *, execute, completed_read, **args):
        if not callable(execute):
            raise TypeError('synchronous audit consumer required')
        read_command = self._commands.read_completed_current if completed_read else self._commands.read_current
        def consume(current):
            saved = read_command(conn, **args)
            if saved.assessment_hash != current.content_hash:
                raise IngressJournalConflict('GROUP_PREPARATION_CHANGED')
            if saved.command is not None:
                completion = self._store.read_batch_projection_completion(saved.command, [])
                if completion['pending']:
                    raise IngressJournalConflict('GROUP_LINK_PROJECTION_PENDING')
            def with_policy(policy_current):
                if policy_current.group != current.input.group:
                    raise IngressJournalConflict('GROUP_POLICY_CHANGED')
                scope = current.input.claim.scope
                _, _, mapping = current.input.group.members[0]
                sync = SyncScope(org_id=scope.org_id, workspace_id=scope.project_id, platform=mapping.platform,
                                 shop_or_marketplace_id=mapping.shop_id, stream='relationship-audit')
                ids = {}
                for (_, _, mapping), parent in zip(current.input.group.members, current.input.parents):
                    objects, _ = _normalize_rows(parent['outputRows'], sync)
                    ids[mapping.read_spec.object_type] = tuple(obj.identity.external_id for obj in objects)
                rules = policy_current.policy.rules
                selectors = tuple((rule.link_type, 'source' if rule.direction == 'row-to-parent' else 'target',
                                   rule.row_type, ids[rule.row_type]) for rule in rules if ids[rule.row_type])
                actual = self._store.read_active_links_for_rows(sync, selectors)
                _, expected_links = _normalize_rows(list(current.assessment.candidate_links), sync)
                expected = {(link.link_type, link.source_type, link.source.external_id, link.target_type, link.target.external_id)
                            for link in expected_links}
                seen = {_identity(row) for row in actual}
                counts, candidates, unresolved = {}, [], []
                for rule in rules:
                    original = current.assessment.counts[rule.link_type]
                    unknown = sum(original[name] for name in ('missingReference', 'invalidReference', 'missingParent'))
                    expected_rule = {key for key in expected if key[0] == rule.link_type}
                    seen_rule = {key for key in seen if key[0] == rule.link_type}
                    extra = seen_rule - expected_rule
                    future = 0
                    for row in actual:
                        if _identity(row) not in extra:
                            continue
                        newer = _db_time(row['source_updated_at']) > current.input.read_completed_at
                        future += int(newer)
                        descriptor = dict(linkType=row['link_type'], sourceType=row['source_object_type'],
                            sourceId=row['source_external_id'], targetType=row['target_object_type'],
                            targetId=row['target_external_id'], payloadHash=row['payload_hash'],
                            sourceUpdatedAt=_db_time(row['source_updated_at']).isoformat())
                        (unresolved if unknown or newer else candidates).append(descriptor)
                    counts[rule.link_type] = dict(expectedActive=len(expected_rule), actualActive=len(seen_rule),
                        missingExpected=len(expected_rule-seen_rule), extraActive=len(extra),
                        uncertainReferences=unknown, futureExtras=future)
                provisional = SnapshotGroupRelationshipAudit(current.content_hash, saved.command_hash, counts,
                    tuple(candidates), tuple(unresolved), '')
                digest = observed_rows_hash([_payload(provisional)])
                result = SnapshotGroupRelationshipAudit(provisional.assessment_hash, provisional.command_hash,
                    counts, provisional.cleanup_candidates, provisional.unresolved_extras, digest)
                value = execute(result)
                _reject_deferred(value)
                if observed_rows_hash([_payload(result)]) != digest:
                    raise ValueError('relationship audit changed during consumption')
                if self._store.read_active_links_for_rows(sync, selectors) != actual:
                    raise IngressJournalConflict('GROUP_RELATIONSHIP_AUDIT_CHANGED')
                if read_command(conn, **args) != saved:
                    raise IngressJournalConflict('GROUP_LINK_PREPARATION_CHANGED')
                return value
            return self._commands._relationships._assessments._policies.run_current(conn, scope=args['scope'],
                refs=tuple(ref for ref, _ in args['bindings']), actor=args['actor'], policy_ref=args['policy_ref'],
                execute=with_policy)
        read = (self._commands._relationships._assessments.run_completed_current if completed_read
                else self._commands._relationships._assessments.run_current)
        return read(conn, **args, execute=consume)
