"""Current original group -> immutable exact command, never apply or reread source."""
from dataclasses import dataclass
from uuid import UUID
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.ec_ingress_recovery import read_saved_projection_completion
from aos_api.ec_ot_writer import _normalize_rows, _build_batch_command
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.ecom_core_models import BatchCommand, SyncScope
from aos_api.extension_runtime.lifecycle_store import _require_transaction
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.pipeline_snapshot_group_relationship_journal import PipelineSnapshotGroupRelationshipJournal
from aos_api.source_read_observation import observed_rows_hash


@dataclass(frozen=True)
class PreparedSnapshotGroupLinkCommand:
    assessment_hash: str
    command_hash: str
    command: BatchCommand | None
    created: bool


class PipelineSnapshotGroupLinkCommandJournal:
    def __init__(self, *, claims, store):
        if type(store) is not EcomConsistencyStore:
            raise TypeError('exact original ConsistencyStore required')
        self._relationships = PipelineSnapshotGroupRelationshipJournal(claims=claims)
        self._claims, self._store = claims, store
        self._schema = claims._journal.schema

    def prepare(self, conn, **args):
        _require_transaction(conn)
        with conn.transaction():
            return self._operate(conn, args, create=True)

    def read_current(self, conn, **args):
        _require_transaction(conn)
        return self._operate(conn, args, create=False)

    def read_completed_current(self, conn, **args):
        _require_transaction(conn)
        return self._operate(conn, args, create=False, completed_read=True)

    def _operate(self, conn, args, *, create, completed_read=False):
        if completed_read and create:
            raise ValueError('completed input cannot prepare link commands')
        def consume(current):
            read = self._relationships.read_completed_current if completed_read else self._relationships.read_current
            relationship = read(conn, **args)
            if relationship.assessment_hash != current.content_hash:
                raise IngressJournalConflict('GROUP_PREPARATION_CHANGED')
            scope = current.input.claim.scope
            for (ref, _, _), parent in zip(current.input.group.members, current.input.parents):
                journal = ControlledIngressJournal(claims=self._claims, scope=scope,
                    run_id=parent['runId'], control_ref=ref, actor=args['actor'],completed_read=completed_read)
                completion = read_saved_projection_completion(conn, scope, parent['runId'], journal=journal, store=self._store)
                if completion['pending'] != 0:
                    raise IngressJournalConflict('GROUP_OBJECT_PROJECTION_PENDING')
            _, draft, mapping = current.input.group.members[0]
            stream_hash = observed_rows_hash([{'installation': draft.installation_ref.installation_id,
                                              'policy': current.policy_ref.resource_id}]).removeprefix('sha256:')
            sync_scope = SyncScope(org_id=scope.org_id, workspace_id=scope.project_id,
                platform=mapping.platform, shop_or_marketplace_id=mapping.shop_id,
                stream='snapshot-group-links:' + stream_hash)
            objects, links = _normalize_rows(list(current.assessment.candidate_links), sync_scope)
            if objects:
                raise IngressJournalConflict('GROUP_RELATIONSHIP_OBJECTS_FORBIDDEN')
            key = 'snapshot-group-links:' + str(UUID(args['group_id'])) + ':' + current.content_hash.removeprefix('sha256:')
            table = sql.Identifier(self._schema, 'pipeline_snapshot_group_link_command')
            with conn.cursor(row_factory=dict_row) as cursor:
                row = cursor.execute(sql.SQL('SELECT assessment_hash,link_count,command_hash,command FROM {} WHERE org_id=%s AND project_id=%s AND group_id=%s').format(table),
                    (*scope.key, UUID(args['group_id']))).fetchone()
                if row is None:
                    if not create:
                        raise LookupError('original group link command required')
                    command = None
                    if links:
                        command = _build_batch_command(sync_scope=sync_scope, objects=[], links=links,
                                                      pipeline_id=sync_scope.stream, store=self._store)
                        command = BatchCommand.model_validate(command.model_dump(mode='python') | {'idempotency_key': key})
                    body = command.model_dump(mode='json') if command else None
                    digest = observed_rows_hash([{'command': body}])
                    cursor.execute(sql.SQL('INSERT INTO {} (org_id,project_id,group_id,assessment_hash,link_count,command_hash,command) VALUES(%s,%s,%s,%s,%s,%s,%s)').format(table),
                        (*scope.key, UUID(args['group_id']), current.content_hash, len(links), digest, Jsonb(body) if body is not None else None))
                    return PreparedSnapshotGroupLinkCommand(current.content_hash, digest, command, True)
                body = row['command']
                if (row['assessment_hash'] != current.content_hash or row['link_count'] != len(links)
                        or row['command_hash'] != observed_rows_hash([{'command': body}])):
                    raise IngressJournalConflict('GROUP_LINK_COMMAND_DRIFT')
                command = BatchCommand.model_validate(body) if body is not None else None
                if links:
                    if (command is None or command.model_dump(mode='json') != body or command.scope != sync_scope
                            or command.objects or command.links != links or command.idempotency_key != key):
                        raise IngressJournalConflict('GROUP_LINK_COMMAND_DRIFT')
                elif command is not None:
                    raise IngressJournalConflict('GROUP_EMPTY_LINK_COMMAND_DRIFT')
                return PreparedSnapshotGroupLinkCommand(current.content_hash, row['command_hash'], command, False)
        read = (self._relationships._assessments.run_completed_current if completed_read
                else self._relationships._assessments.run_current)
        return read(conn, **args, execute=consume)
