"""Read-only routing from an original run to its immutable input group.

This locator supplies no current authorization. Its caller must use the original
group Owner before consuming data or executing anything with the returned route.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from psycopg import sql
from psycopg.rows import dict_row

from aos_api.ec_ingress_journal import _digest
from aos_api.extension_runtime.lifecycle_store import _require_transaction
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner, _text
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True)
class SnapshotGroupRoute:
    group_id: str
    actor: str
    bindings: tuple[tuple[PipelineExactRef, str], ...]
    manifest_hash: str
    read_started_at: datetime
    read_completed_at: datetime


class PipelineSnapshotGroupLocator:
    def __init__(self, *, claims):
        if type(claims) is not PipelineSourceClaimOwner:
            raise TypeError('original source claim Owner required')
        self._schema = claims._journal.schema

    def read(self, conn, *, scope, run_id, expected_cutoff):
        if type(expected_cutoff) is not datetime or expected_cutoff.utcoffset() is None:
            raise ValueError('aware original cutoff required')
        route = self.discover(conn, scope=scope, run_id=run_id)
        if route is not None and route.read_completed_at != expected_cutoff:
            raise ValueError('original snapshot cutoff differs')
        return route

    def discover(self, conn, *, scope, run_id):
        """Find the saved source clock; this is not current execution authority."""
        _require_transaction(conn)
        if type(scope) is not TenantScope:
            raise TypeError('exact route tenant required')
        run_id = _text(run_id, 200)
        with conn.cursor(row_factory=dict_row) as cursor:
            identity = cursor.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
                "current_setting('aos.project_id',true) AS project_id").fetchone()
            if (identity['role'], identity['org_id'], identity['project_id']) != ('aos_runtime', *scope.key):
                raise PermissionError('current runtime route tenant required')
            rows = cursor.execute(sql.SQL('''SELECT c.group_id,c.actor,c.request_hash,c.member_count,c.binding,
                    i.request_hash AS input_request_hash,i.manifest_hash,i.manifest,
                    i.read_started_at,i.read_completed_at,i.snapshot_basis
                FROM {member} m JOIN {claim} c USING(org_id,project_id,group_id)
                JOIN {input} i USING(org_id,project_id,group_id)
                WHERE m.org_id=%s AND m.project_id=%s AND m.run_id=%s LIMIT 2''').format(
                member=sql.Identifier(self._schema,'pipeline_snapshot_group_member'),
                claim=sql.Identifier(self._schema,'pipeline_snapshot_group_claim'),
                input=sql.Identifier(self._schema,'pipeline_snapshot_group_input')),
                (*scope.key,run_id)).fetchall()
            if not rows:
                return None
            if len(rows) != 1:
                raise ValueError('ambiguous original snapshot group')
            row = rows[0]
            group_id = str(UUID(str(row['group_id'])))
            actor = _text(row['actor'],240)
            body = row['binding']
            manifest = row['manifest']
            if (type(body) is not dict or set(body) != {'schemaVersion','orgId','projectId','groupId','actor','members'}
                or body['schemaVersion'] != 'aos.snapshot-group-claim/v1'
                or (body['orgId'],body['projectId'],body['groupId'],body['actor']) != (*scope.key,group_id,actor)
                or row['request_hash'] != 'sha256:'+_digest(body)
                or row['input_request_hash'] != row['request_hash']
                or type(body['members']) is not list or not 1 <= len(body['members']) <= 12
                or len(body['members']) != row['member_count']
                or type(manifest) is not dict or set(manifest) != {'members'}
                or type(manifest['members']) is not list or len(manifest['members']) != row['member_count']
                or row['manifest_hash'] != 'sha256:'+_digest(manifest)):
                raise ValueError('original group route binding differs')
            bindings = []
            for member, leaf in zip(body['members'], manifest['members']):
                if (type(member) is not dict or set(member) != {'runId','controlRef','draft'}
                    or type(leaf) is not dict or set(leaf) != {'runId','envelopeHash','rowsHash','rowCount'}
                    or member['runId'] != leaf['runId']):
                    raise ValueError('original group route member differs')
                ref = PipelineExactRef.model_validate(member['controlRef'])
                if ref.resource_type != 'PipelineRuntimeControlRevision':
                    raise ValueError('original runtime control reference required')
                bindings.append((ref, _text(member['runId'],200)))
            runs = tuple(run for _,run in bindings)
            if len(set(runs)) != len(runs) or run_id not in runs:
                raise ValueError('unique original group runs required')
            saved = cursor.execute(sql.SQL('''SELECT ordinal,run_id FROM {} WHERE
                org_id=%s AND project_id=%s AND group_id=%s ORDER BY ordinal LIMIT 13''').format(
                sql.Identifier(self._schema,'pipeline_snapshot_group_member')),
                (*scope.key,UUID(group_id))).fetchall()
            if [(r['ordinal'],r['run_id']) for r in saved] != list(enumerate(runs,1)):
                raise ValueError('original member index differs from binding')
            if (row['snapshot_basis'] != 'innodb-repeatable-read'
                or row['read_started_at'] > row['read_completed_at']):
                raise ValueError('original snapshot cutoff differs')
            return SnapshotGroupRoute(group_id, actor, tuple(bindings), row['manifest_hash'],
                row['read_started_at'], row['read_completed_at'])
