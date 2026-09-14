"""Native public schema/Owners; installed asset checks remain named fixtures.

No source call, SQL namespace replacement, fixture DDL, privilege expansion or
Task writes. The original stored fixture rolls back its complete transaction.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from test_product_event_control_host_service import (
    host_case, control_governed, governed, service_case, stored, pair, body,
)
from test_pipeline_snapshot_group_owner_pg import mapping
from tests.test_pipeline_runtime_control_contracts import payload
from aos_api.ec_ingress_journal import _digest
from aos_api.ecom_core_models import REQUIRED_PROPERTIES
from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft, PipelineRuntimeControlDraft
from aos_api.pipeline_runtime_control_owner import PipelineRuntimeControlOwner
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.pipeline_snapshot_group_claim_owner import PipelineSnapshotGroupClaimOwner
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES
from aos_api.tenant_scope import TenantScope


@pytest.fixture
def native_claims_case(host_case):
    conn, _, _, dispatch, _ = host_case
    assert conn.execute('SELECT current_database() AS db').fetchone()['db'].endswith('_ti4_test')
    assert conn.execute('SELECT current_schema() AS schema').fetchone()['schema'] == 'public'
    scope = TenantScope('org-org', 'dev-project')
    actor, source_id = 'fixture-host', 'native-twelve-source'
    conn.execute('RESET ROLE')
    # The original source trigger, rather than a made-up revision history.
    revision = conn.execute('''INSERT INTO meta_source(id,org_id,project_id,type,status)
        VALUES(%s,%s,%s,'jdbc-mysql-ssh','registered') RETURNING configuration_revision''',
        (source_id, *scope.key)).fetchone()['configuration_revision']
    plans = {}
    selections = object.__new__(PipelineSourceSelectionOwner)
    def named_assets(db, draft, executor, consume, *, snapshot=False):
        assert db is conn and executor == actor
        plan = plans[draft.pipeline_id]
        return consume(plan if snapshot else plan.read_spec)
    selections._guarded = named_assets
    controls = PipelineRuntimeControlOwner(selections=selections)
    bindings = []
    for index, source in enumerate(CANONICAL_QYH_SOURCES):
        base = mapping('native_table_' + str(index))
        defaults = {key: 1 for key in REQUIRED_PROPERTIES[source.object_type]
                    if key not in {'createdAt', 'updatedAt', 'name', 'shippedAt'}}
        defaults.update(status='active', currency='CNY', timezone='+08:00')
        plans[source.pipeline_id] = replace(base,
            read_spec=replace(base.read_spec, object_type=source.object_type),
            defaults=tuple(defaults.items()))
        graph = dict(pipeline_id=source.pipeline_id, write_mode='SNAPSHOT', nodes=[dict(
            id='source-node', name='source', pipeline_id=source.pipeline_id,
            node_type='source', config=dict(source_id=source_id))])
        schedule, run = 'native-schedule-' + str(index), 'native-run-' + str(index)
        conn.execute('RESET ROLE')
        conn.execute('''INSERT INTO meta_pipeline(id,org_id,project_id,source_id)
            VALUES(%s,%s,%s,%s)''', (source.pipeline_id,*scope.key,source_id))
        conn.execute('''INSERT INTO meta_schedule(id,org_id,project_id,pipeline_id,enabled,ingest)
            VALUES(%s,%s,%s,%s,true,%s)''',
            (schedule,*scope.key,source.pipeline_id,Jsonb(dict(kind='pipeline-live-v1',pipelineId=source.pipeline_id))))
        conn.execute('''INSERT INTO meta_schedule_run(id,org_id,project_id,schedule_id,scheduled_for,trigger,status)
            VALUES(%s,%s,%s,%s,clock_timestamp(),'manual','running')''', (run,*scope.key,schedule))
        conn.execute('''INSERT INTO phase5_pipeline_graph(pipeline_id,org_id,project_id,revision,payload)
            VALUES(%s,%s,%s,1,%s)''', (source.pipeline_id,*scope.key,Jsonb(graph)))
        conn.execute('SET LOCAL ROLE aos_runtime')
        draft = payload()
        draft.pop('sourceSelectionRef')
        draft.update(orgId=scope.org_id,projectId=scope.project_id,pipelineId=source.pipeline_id,
            sourceId=source_id,graphHash=_digest(graph),generation=str(dispatch.generation),
            executionEpoch=dispatch.execution_epoch,notBefore=datetime.now(timezone.utc)-timedelta(minutes=1),
            expiresAt=datetime.now(timezone.utc)+timedelta(hours=1))
        draft['installationRef']['installationId'] = str(dispatch.installation_id)
        draft['sourceConfigurationRef']['resourceId'] = 'source-config-' + str(revision)
        selected = PipelineSourceSelectionDraft.model_validate(draft)
        with conn.transaction():
            reference = selections.append(conn,draft=selected,actor=actor,idempotency_key='native-selection-'+str(index))
            control = PipelineRuntimeControlDraft.model_validate(dict(
                selected.model_dump(exclude={'schema_version'}),source_selection_ref=reference))
            reference = controls.append(conn,draft=control,actor=actor,idempotency_key='native-control-'+str(index))
        bindings.append((reference,run))
    claims = PipelineSourceClaimOwner(controls=controls)
    assert claims._journal.schema == 'public'
    owner = PipelineSnapshotGroupClaimOwner(claims=claims)
    args = dict(scope=scope, actor=actor, group_id=str(uuid4()), bindings=tuple(bindings))
    return conn,owner,args,source_id,revision


def test_native_twelve_claims_replay_exactly(native_claims_case):
    conn,owner,args,source,revision = native_claims_case
    with conn.transaction():
        first = owner.reserve(conn,**args)
        second = owner.reserve(conn,**args)
        current = owner.read_current(conn,**args)
    assert first.created and not second.created and first.record == second.record == current
    assert len(current.members) == 12 and all(item.call_ordinal == 1 for item in current.members)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n'] == 12
    history = conn.execute('''SELECT revision_id FROM data_source_configuration_revision
        WHERE org_id=%s AND project_id=%s AND source_id=%s''', (*args['scope'].key,source)).fetchall()
    assert history == [dict(revision_id=revision)]


@pytest.mark.parametrize('fault', ['source-version', 'tenant'])
def test_native_current_drift_rejects_replay(native_claims_case,fault):
    conn,owner,args,source,original_revision = native_claims_case
    with conn.transaction():
        owner.reserve(conn,**args)
    with pytest.raises((ValueError,RuntimeError,PermissionError,LookupError)), conn.transaction():
        if fault == 'source-version':
            conn.execute('RESET ROLE')
            changed = conn.execute('''UPDATE meta_source SET props=%s WHERE id=%s
                RETURNING configuration_revision''', (Jsonb(dict(fixtureRevision=2)),source)).fetchone()
            assert changed['configuration_revision'] != original_revision
            assert conn.execute('''SELECT count(*) AS n FROM data_source_configuration_revision
                WHERE source_id=%s''', (source,)).fetchone()['n'] == 2
            conn.execute('SET LOCAL ROLE aos_runtime')
        else:
            conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
        owner.read_current(conn,**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n'] == 12


def test_native_outer_failure_rolls_back_all_twelve(native_claims_case):
    conn,owner,args,_,_ = native_claims_case
    with pytest.raises(RuntimeError,match='native outer rollback'),conn.transaction():
        owner.reserve(conn,**args)
        raise RuntimeError('native outer rollback')
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n'] == 0
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_claim').fetchone()['n'] == 0
