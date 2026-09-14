"""Only present-row relationship residuals; no deletion or source reads."""
import pytest
from test_lifecycle_pg import database, pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_snapshot_group_claim_owner_pg import group_claim_case
from test_controlled_snapshot_group_ingress_pg import prepared_case
from test_snapshot_group_assessment_owner_pg import assessment_case
from test_snapshot_group_relationship_journal_pg import journal_case
from test_snapshot_group_object_executor_pg import object_case
from test_snapshot_group_link_command_pg import link_case
from test_snapshot_group_link_executor_pg import link_executor_case
from aos_api.pipeline_snapshot_group_relationship_audit import PipelineSnapshotGroupRelationshipAudit


@pytest.fixture
def audit_case(link_executor_case):
    executor, conn, args, state = link_executor_case
    owner = PipelineSnapshotGroupRelationshipAudit(claims=executor._objects._claims, store=executor._store)
    return executor, conn, args, state, owner


def test_current_correct_candidates_have_no_residuals(audit_case):
    executor, conn, args, state, owner = audit_case
    executor.execute(**args)
    with conn.transaction(): result = owner.read_current(conn, **args)
    assert result.counts['Shop.hasWeapp']['extraActive'] == 0
    assert result.counts['Shop.hasWeapp']['missingExpected'] == 0
    assert result.cleanup_candidates == () and result.unresolved_extras == ()
    assert state['calls'] == 1


def add_extra(executor, args, *, future=False):
    from datetime import timedelta
    from aos_api.ec_ot_writer import _build_batch_command
    from aos_api.ecom_core_models import BatchCommand
    with executor._transaction(args['scope']) as db:
        prepared = executor._commands.read_current(db, **args)
        current = executor._commands._relationships._assessments.run_current(db, **args, execute=lambda v: v)
    command = prepared.command
    original = next(BatchCommand.model_validate(parent['command']) for parent in current.input.parents
                    if parent.get('command', {}).get('objects', [{}])[0].get('object_type') == 'Shop')
    shop = original.objects[0]
    other = shop.model_copy(update={'identity': shop.identity.model_copy(update={'external_id': 'niushop:1:9999'})})
    old_link = command.links[0].model_copy(update={'source': other.identity,
        'source_updated_at': command.links[0].source_updated_at + (timedelta(seconds=1) if future else timedelta(0)),
        'cursor_external_id': 'old-parent-fixture'})
    batch = _build_batch_command(sync_scope=command.scope.model_copy(update={'stream': 'old-parent-fixture'}),
        objects=[other], links=[old_link], pipeline_id='old-parent-fixture', store=executor._store)
    executor._store.apply_batch(batch)
    return command, old_link


def test_present_child_old_parent_is_reported_without_deletion(audit_case):
    executor, conn, args, state, owner = audit_case
    executor.execute(**args)
    command, old_link = add_extra(executor, args)
    with conn.transaction(): result = owner.read_current(conn, **args)
    assert result.counts['Shop.hasWeapp']['extraActive'] == 1
    assert len(result.cleanup_candidates) == 1 and not result.unresolved_extras
    assert result.cleanup_candidates[0]['sourceId'] == old_link.source.external_id
    assert conn.execute('SELECT count(*) AS n FROM ecom_link WHERE deleted_at IS NULL').fetchone()['n'] == 2
    assert state['calls'] == 1


def test_relation_newer_than_source_observation_is_unresolved(audit_case):
    executor, conn, args, _, owner = audit_case
    executor.execute(**args)
    add_extra(executor, args, future=True)
    with conn.transaction(): result = owner.read_current(conn, **args)
    assert not result.cleanup_candidates and len(result.unresolved_extras) == 1
    assert result.counts['Shop.hasWeapp']['futureExtras'] == 1


def test_unapplied_links_cannot_be_audited_as_ready(audit_case):
    from aos_api.ecom_core_models import EcomConsistencyError
    executor, conn, args, _, owner = audit_case
    executor._objects.execute(**args)
    with executor._transaction(args['scope']) as db: executor._commands.prepare(db, **args)
    with pytest.raises(EcomConsistencyError), conn.transaction(): owner.read_current(conn, **args)


def test_current_denial_and_callback_mutation_are_rejected(audit_case):
    executor, conn, args, state, owner = audit_case
    executor.execute(**args)
    def mutate(result): result.counts['Shop.hasWeapp']['extraActive'] = 999
    with pytest.raises(ValueError, match='changed'), conn.transaction(): owner.run_current(conn, **args, execute=mutate)
    state['deny'] = True
    with pytest.raises(PermissionError), conn.transaction(): owner.read_current(conn, **args)


def test_bounded_store_query_cannot_widen_empty_or_foreign_rows(audit_case):
    from aos_api.ecom_core_models import EcomConsistencyError
    executor, conn, args, _, owner = audit_case
    executor.execute(**args)
    command, _ = add_extra(executor, args)
    selector = ('Shop.hasWeapp', 'target', 'Weapp', (command.links[0].target.external_id,))
    read = executor._store.read_active_links_for_rows
    assert read(command.scope, ()) == ()
    assert read(command.scope.model_copy(update={'workspace_id': 'other'}), (selector,)) == ()
    assert read(command.scope.model_copy(update={'shop_or_marketplace_id': 'other'}), (selector,)) == ()
    with pytest.raises(ValueError): read(command.scope, (('Shop.hasWeapp','target','Weapp',()),))
    with pytest.raises(EcomConsistencyError): read(command.scope, (selector,), limit=1)


def test_unobserved_child_and_deleted_old_edge_are_excluded(audit_case):
    from datetime import timedelta
    from aos_api.ec_ot_writer import _build_batch_command
    from aos_api.ecom_core_models import BatchCommand
    executor, conn, args, _, owner = audit_case
    executor.execute(**args)
    command, old_link = add_extra(executor, args)
    with executor._transaction(args['scope']) as db:
        current = executor._commands._relationships._assessments.run_current(db, **args, execute=lambda v: v)
    original = next(BatchCommand.model_validate(parent['command']) for parent in current.input.parents
                    if parent['command']['objects'][0]['object_type'] == 'Weapp')
    child = original.objects[0]
    other = child.model_copy(update={'identity': child.identity.model_copy(update={'external_id': 'niushop:1:7777'})})
    unrelated_link = command.links[0].model_copy(update={'target': other.identity, 'cursor_external_id': 'unobserved-fixture'})
    unrelated = _build_batch_command(sync_scope=command.scope.model_copy(update={'stream':'unobserved-fixture'}),
        objects=[other], links=[unrelated_link], pipeline_id='unobserved-fixture', store=executor._store)
    executor._store.apply_batch(unrelated)
    tombstone = old_link.model_copy(update={'is_deleted':True, 'source_updated_at':old_link.source_updated_at+timedelta(seconds=1)})
    removed = _build_batch_command(sync_scope=command.scope.model_copy(update={'stream':'old-parent-fixture'}),
        objects=[], links=[tombstone], pipeline_id='old-parent-fixture', store=executor._store)
    executor._store.apply_strict_link_batch(removed)
    with conn.transaction(): result = owner.read_current(conn, **args)
    assert result.counts['Shop.hasWeapp']['actualActive'] == 1
    assert not result.cleanup_candidates and not result.unresolved_extras
    assert conn.execute('SELECT count(*) AS n FROM ecom_link WHERE deleted_at IS NULL').fetchone()['n'] == 2


def test_missing_parent_reference_keeps_extra_unresolved(assessment_case, monkeypatch):
    from dataclasses import replace
    from aos_api import pipeline_controlled_snapshot_group_ingress as ingress
    from aos_api.ecom_core_models import BatchCommand, CoreLinkRecord
    from aos_api.ec_ot_writer import _build_batch_command
    from tests.test_ecom_consistency_store import obj
    source = ingress.read_selected_snapshot_group
    def missing_shop(**kwargs):
        result = source(**kwargs)
        rows = dict(result.rows_by_table)
        for _, _, mapping in kwargs['group'].members:
            if mapping.read_spec.object_type == 'Shop': rows[mapping.read_spec.table] = []
        return replace(result, rows_by_table=rows)
    monkeypatch.setattr(ingress, 'read_selected_snapshot_group', missing_shop)
    prepared = journal_case.__wrapped__(assessment_case)
    generator = object_case.__wrapped__(prepared)
    original = next(generator)
    try:
        base = link_case.__wrapped__(original)
        executor, conn, args, state, owner = audit_case.__wrapped__(link_executor_case.__wrapped__(base))
        executor.execute(**args)
        with executor._transaction(args['scope']) as db:
            current = executor._commands._relationships._assessments.run_current(db, **args, execute=lambda v: v)
        command = next(BatchCommand.model_validate(parent['command']) for parent in current.input.parents if parent.get('command') is not None)
        child = command.objects[0]
        shop = obj('Shop', 'unused', identity=child.identity.model_copy(update={'external_id':'niushop:1:9999'}),
                   when=current.input.read_completed_at)
        link = CoreLinkRecord(link_type='Shop.hasWeapp', source_type='Shop', source=shop.identity,
            target_type='Weapp', target=child.identity, source_updated_at=current.input.read_completed_at,
            cursor_external_id='unresolved-fixture')
        extra = _build_batch_command(sync_scope=command.scope.model_copy(update={'stream':'unresolved-fixture'}),
            objects=[shop], links=[link], pipeline_id='unresolved-fixture', store=executor._store)
        executor._store.apply_batch(extra)
        with conn.transaction(): result = owner.read_current(conn, **args)
        assert result.counts['Shop.hasWeapp']['uncertainReferences'] == 1
        assert not result.cleanup_candidates and len(result.unresolved_extras) == 1
        assert state['calls'] == 1
    finally:
        try: next(generator)
        except StopIteration: pass
