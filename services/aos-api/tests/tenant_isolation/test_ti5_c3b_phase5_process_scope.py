from __future__ import annotations

import pytest

from aos_api.phase5_pipeline_engine import get_engine
from aos_api.tenant_scope import TenantScope


SCOPE_A = TenantScope("org-phase5-a", "workspace-phase5-a")
SCOPE_B = TenantScope("org-phase5-b", "workspace-phase5-b")


@pytest.fixture(autouse=True)
def _reset_engine() -> None:
    engine = get_engine()
    engine.reset_all_for_tests()
    yield
    engine.reset_all_for_tests()


def _seed(scope: TenantScope, label: str) -> tuple[str, str, str, str]:
    engine = get_engine()
    pipeline = engine.create_pipeline(scope, id="shared-pipeline", name=label)
    node = engine.add_node(
        scope,
        pipeline.id,
        label,
        id="shared-node",
        node_type="transform",
        config={"tenant": label},
    )
    engine.add_edge(
        scope,
        pipeline.id,
        node.id,
        node.id + "-sink",
        id="shared-edge",
    )
    proposal = engine.create_proposal(
        scope, pipeline.id, label, id="shared-proposal"
    )
    schedule = engine.create_schedule(
        scope,
        id="shared-schedule",
        name=label,
        pipeline_id=pipeline.id,
    )
    return pipeline.id, node.id, proposal.id, schedule.id


def test_phase5_same_ids_coexist_and_all_reads_are_scope_bound() -> None:
    engine = get_engine()
    ids_a = _seed(SCOPE_A, "A")
    ids_b = _seed(SCOPE_B, "B")
    assert ids_a == ids_b

    pipeline_id, node_id, proposal_id, schedule_id = ids_a
    assert engine.get_pipeline(SCOPE_A, pipeline_id).name == "A"
    assert engine.get_pipeline(SCOPE_B, pipeline_id).name == "B"
    assert engine.get_node(SCOPE_A, node_id).config == {"tenant": "A"}
    assert engine.get_node(SCOPE_B, node_id).config == {"tenant": "B"}
    assert engine.get_proposal(SCOPE_A, proposal_id).title == "A"
    assert engine.get_proposal(SCOPE_B, proposal_id).title == "B"
    assert engine.get_schedule(SCOPE_A, schedule_id).name == "A"
    assert engine.get_schedule(SCOPE_B, schedule_id).name == "B"
    assert engine.list_history(SCOPE_A, pipeline_id)[0].pipeline_id == pipeline_id
    assert engine.list_history(SCOPE_B, pipeline_id)[0].pipeline_id == pipeline_id


def test_schedule_run_and_reset_do_not_cross_scope() -> None:
    engine = get_engine()
    pipeline_id, _, _, schedule_id = _seed(SCOPE_A, "A")
    _seed(SCOPE_B, "B")

    run_a = engine.run_schedule(SCOPE_A, schedule_id)
    run_b = engine.run_schedule(SCOPE_B, schedule_id)
    assert run_a.status == run_b.status == "unsupported"
    assert len(engine.list_schedule_runs(SCOPE_A, schedule_id)) == 1
    assert len(engine.list_schedule_runs(SCOPE_B, schedule_id)) == 1

    engine.reset(scope=SCOPE_A)
    assert engine.get_pipeline(SCOPE_A, pipeline_id) is None
    assert engine.get_schedule(SCOPE_A, schedule_id) is None
    assert engine.get_pipeline(SCOPE_B, pipeline_id).name == "B"
    assert engine.get_schedule(SCOPE_B, schedule_id).name == "B"
    assert len(engine.list_schedule_runs(SCOPE_B, schedule_id)) == 1


def test_foreign_child_ids_are_not_visible_without_local_parent() -> None:
    engine = get_engine()
    pipeline_id, node_id, proposal_id, schedule_id = _seed(SCOPE_A, "A")

    assert engine.get_pipeline(SCOPE_B, pipeline_id) is None
    assert engine.get_node(SCOPE_B, node_id) is None
    assert engine.get_proposal(SCOPE_B, proposal_id) is None
    assert engine.get_schedule(SCOPE_B, schedule_id) is None
    with pytest.raises(KeyError):
        engine.preview_node(SCOPE_B, pipeline_id, node_id)
    with pytest.raises(KeyError):
        engine.run_schedule(SCOPE_B, schedule_id)
