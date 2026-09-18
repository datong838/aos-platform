"""Persist exact current retirement, and recover its original conditional Receipt."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.ec_ot_writer import _normalize_rows, _build_batch_command
from aos_api.ecom_consistency_store import _db_time
from aos_api.ecom_core_models import BatchCommand, CoreLinkRecord, StorageIdentity, SyncScope
from aos_api.extension_runtime.lifecycle_store import _require_transaction
from aos_api.pipeline_snapshot_group_relationship_audit import PipelineSnapshotGroupRelationshipAudit, _payload
from aos_api.source_read_observation import observed_rows_hash


@dataclass(frozen=True)
class PreparedSnapshotGroupRetirement:
    audit_hash: str
    preparation_hash: str
    command: BatchCommand | None
    created: bool
    applied: bool


def _envelope(parent_hash, audit_hash, audit, prepared_at, command):
    return dict(parentCommandHash=parent_hash, auditHash=audit_hash, audit=audit,
                preparedAt=prepared_at.isoformat(), command=command)


class PipelineSnapshotGroupRetirementJournal:
    def __init__(self, *, claims, store):
        self._audit = PipelineSnapshotGroupRelationshipAudit(claims=claims, store=store)
        self._commands = self._audit._commands
        self._store, self._schema = store, claims._journal.schema

    def prepare(self, conn, **args):
        _require_transaction(conn)
        with conn.transaction(): return self._operate(conn, args, create=True)

    def read_current(self, conn, **args):
        _require_transaction(conn)
        return self._operate(conn, args, create=False)

    def read_completed_current(self, conn, **args):
        _require_transaction(conn)
        return self._operate(conn, args, create=False, completed_read=True)

    def _operate(self, conn, args, *, create, completed_read=False):
        if completed_read and create:
            raise ValueError('completed input cannot prepare retirement')
        read_command = self._commands.read_completed_current if completed_read else self._commands.read_current
        read_audit = self._audit.run_completed_current if completed_read else self._audit.run_current
        def consume(current):
            def policy_guard(policy_current):
                if policy_current.group != current.input.group or policy_current.policy.retirement_mode != 'present-rows-only':
                    raise PermissionError('current explicit retirement policy required')
                parent = read_command(conn, **args)
                if parent.assessment_hash != current.content_hash:
                    raise IngressJournalConflict('GROUP_PREPARATION_CHANGED')
                if parent.command is not None and self._store.read_batch_projection_completion(parent.command, [])['pending']:
                    raise IngressJournalConflict('GROUP_LINK_PROJECTION_PENDING')
                scope = current.input.claim.scope
                group_id = UUID(args['group_id'])
                table = sql.Identifier(self._schema, 'pipeline_snapshot_group_retirement')
                with conn.cursor(row_factory=dict_row) as cursor:
                    row = cursor.execute(sql.SQL('SELECT parent_command_hash,audit_hash,audit,prepared_at,preparation_hash,command FROM {} WHERE org_id=%s AND project_id=%s AND group_id=%s').format(table), (*scope.key, group_id)).fetchone()
                    if row is None:
                        if not create: raise LookupError('original retirement preparation required')
                        def save(audit):
                            body = _payload(audit)
                            if audit.assessment_hash != current.content_hash or audit.command_hash != parent.command_hash:
                                raise IngressJournalConflict('RETIREMENT_AUDIT_BINDING_DRIFT')
                            at = _db_time(conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'])
                            sync, links = self._links(current, policy_current.policy, body, audit.content_hash, at)
                            command = None
                            if links:
                                command = _build_batch_command(sync_scope=sync, objects=[], links=links,
                                    pipeline_id=sync.stream, store=self._store)
                                command = BatchCommand.model_validate(command.model_dump(mode='python') | {
                                    'idempotency_key': self._key(group_id, audit.content_hash)})
                            raw = command.model_dump(mode='json') if command else None
                            digest = observed_rows_hash([_envelope(parent.command_hash, audit.content_hash, body, at, raw)])
                            cursor.execute(sql.SQL('INSERT INTO {} (org_id,project_id,group_id,parent_command_hash,audit_hash,audit,prepared_at,preparation_hash,command) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)').format(table),
                                (*scope.key, group_id, parent.command_hash, audit.content_hash, Jsonb(body), at, digest, Jsonb(raw) if raw is not None else None))
                            return PreparedSnapshotGroupRetirement(audit.content_hash, digest, command, True, False)
                        return read_audit(conn, **args, execute=save)
                body, audit_hash = row['audit'], row['audit_hash']
                at = _db_time(row['prepared_at'])
                raw = row['command']
                if (row['parent_command_hash'] != parent.command_hash or body.get('assessmentHash') != current.content_hash
                        or body.get('commandHash') != parent.command_hash or observed_rows_hash([body]) != audit_hash
                        or row['preparation_hash'] != observed_rows_hash([_envelope(parent.command_hash, audit_hash, body, at, raw)])
                        or at > _db_time(conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'])):
                    raise IngressJournalConflict('RETIREMENT_PREPARATION_DRIFT')
                sync, links = self._links(current, policy_current.policy, body, audit_hash, at)
                command = BatchCommand.model_validate(raw) if raw is not None else None
                if links:
                    if (command is None or command.model_dump(mode='json') != raw or command.scope != sync
                            or command.objects or command.links != links or command.idempotency_key != self._key(group_id, audit_hash)):
                        raise IngressJournalConflict('RETIREMENT_COMMAND_DRIFT')
                elif command is not None: raise IngressJournalConflict('EMPTY_RETIREMENT_COMMAND_DRIFT')
                applied = command is not None and self._store.read_committed_link_retirement(command) is not None
                if not applied:
                    def same_audit(audit):
                        if audit.content_hash != audit_hash or _payload(audit) != body:
                            raise IngressJournalConflict('RETIREMENT_PRIOR_AUDIT_CHANGED')
                    read_audit(conn, **args, execute=same_audit)
                return PreparedSnapshotGroupRetirement(audit_hash, row['preparation_hash'], command, False, applied)
            return self._commands._relationships._assessments._policies.run_current(conn, scope=args['scope'],
                refs=tuple(ref for ref, _ in args['bindings']), actor=args['actor'], policy_ref=args['policy_ref'], execute=policy_guard)
        read = (self._commands._relationships.run_completed_current if completed_read
                else self._commands._relationships.run_current)
        return read(conn, **args, execute=consume)

    @staticmethod
    def _key(group_id, audit_hash):
        return 'snapshot-group-retirement:' + str(group_id) + ':' + audit_hash.removeprefix('sha256:')

    @staticmethod
    def _links(current, policy, audit, audit_hash, at):
        if at <= current.input.read_completed_at:
            raise IngressJournalConflict('RETIREMENT_OBSERVATION_TIME_REQUIRED')
        fields = {'assessmentHash','commandHash','counts','cleanupCandidates','unresolvedExtras'}
        if (type(audit) is not dict or set(audit) != fields or type(audit['cleanupCandidates']) is not list
                or len(audit['cleanupCandidates']) > 24000):
            raise IngressJournalConflict('RETIREMENT_AUDIT_SHAPE_INVALID')
        scope = current.input.claim.scope
        _, draft, mapping = current.input.group.members[0]
        stream_hash = observed_rows_hash([{'installation':draft.installation_ref.installation_id,
                                          'policy':current.policy_ref.resource_id}]).removeprefix('sha256:')
        sync = SyncScope(org_id=scope.org_id, workspace_id=scope.project_id, platform=mapping.platform,
                         shop_or_marketplace_id=mapping.shop_id, stream='snapshot-group-retirement:'+stream_hash)
        rows = {}
        for (_, _, plan), parent in zip(current.input.group.members, current.input.parents):
            objects, _ = _normalize_rows(parent['outputRows'], sync)
            rows[plan.read_spec.object_type] = {obj.identity.external_id for obj in objects}
        _, candidates = _normalize_rows(list(current.assessment.candidate_links), sync)
        wanted = {(link.link_type, link.source.external_id, link.target.external_id) for link in candidates}
        rules = {rule.link_type:rule for rule in policy.rules}
        links, identities = [], set()
        for item in audit['cleanupCandidates']:
            expected = {'linkType','sourceType','sourceId','targetType','targetId','payloadHash','sourceUpdatedAt'}
            if type(item) is not dict or set(item) != expected: raise IngressJournalConflict('RETIREMENT_LINK_SHAPE_INVALID')
            rule = rules.get(item['linkType'])
            identity = (item['linkType'], item['sourceId'], item['targetId'])
            if rule is None or identity in identities or identity in wanted:
                raise IngressJournalConflict('RETIREMENT_LINK_SCOPE_INVALID')
            identities.add(identity)
            source_type, target_type = ((rule.row_type, rule.parent_type) if rule.direction=='row-to-parent' else (rule.parent_type, rule.row_type))
            row_id = item['sourceId'] if rule.direction=='row-to-parent' else item['targetId']
            counts = current.assessment.counts[rule.link_type]
            prior_time = datetime.fromisoformat(item['sourceUpdatedAt'])
            if ((item['sourceType'],item['targetType']) != (source_type,target_type)
                    or row_id not in rows[rule.row_type] or prior_time.utcoffset() is None
                    or prior_time > current.input.read_completed_at
                    or any(counts[key] for key in ('missingReference','invalidReference','missingParent'))
                    or type(item['payloadHash']) is not str or len(item['payloadHash'])!=64
                    or any(c not in '0123456789abcdef' for c in item['payloadHash'])):
                raise IngressJournalConflict('RETIREMENT_LINK_NOT_ELIGIBLE')
            common=dict(org_id=scope.org_id,workspace_id=scope.project_id,platform=sync.platform,shop_or_marketplace_id=sync.shop_or_marketplace_id)
            links.append(CoreLinkRecord(link_type=rule.link_type,source_type=source_type,target_type=target_type,
                source=StorageIdentity(**common,external_id=item['sourceId']),target=StorageIdentity(**common,external_id=item['targetId']),
                source_updated_at=at,source_timezone='+00:00',cursor_external_id='retire:'+observed_rows_hash([item]).removeprefix('sha256:'),
                is_deleted=True,properties=dict(retirementExpectedPayloadHash=item['payloadHash'],retirementAuditHash=audit_hash,
                    retirementAssessmentHash=current.content_hash,retirementInputManifestHash=current.input.manifest_hash,
                    sourceModificationTimeKnown=False,sourceUpdatedAtBasis='relationship_retirement_observation')))
        return sync, links
