"""W2-J · OMA 编辑器增强测试：#28+#34 Property Editor + #35 Proposals."""
from __future__ import annotations

import pytest

from aos_api.oma_editor import (
    PropertyEditor,
    PropertyEditorEngine,
    PropertyEditorError,
    Proposal,
    ProposalEngine,
    ProposalError,
    ProposalStatus,
)


# ── #28+#34 Property Editor ──
def test_property_create_basic():
    eng = PropertyEditorEngine()
    prop = eng.create(PropertyEditor(
        object_type="Employee",
        name="email",
        data_type="string",
        backing_column="email_addr",
        backing_dataset="ds-emp",
    ))
    assert prop.id.startswith("prop-")
    assert prop.object_type == "Employee"
    assert prop.backing_column == "email_addr"
    assert prop.origin == "manual"


def test_property_create_with_tsp():
    eng = PropertyEditorEngine()
    prop = eng.create(PropertyEditor(
        object_type="Sensor",
        name="temperature",
        data_type="timeseries",
        is_tsp=True,
        tsp_config={"frequency": "1m", "aggregation": "avg"},
    ))
    assert prop.is_tsp is True
    assert prop.tsp_config["frequency"] == "1m"


def test_property_tsp_type_mismatch():
    eng = PropertyEditorEngine()
    with pytest.raises(PropertyEditorError) as exc:
        eng.create(PropertyEditor(
            object_type="Sensor",
            name="temp",
            data_type="string",
            is_tsp=True,
        ))
    assert exc.value.code == "TSP_TYPE_MISMATCH"


def test_property_title_key_unique():
    eng = PropertyEditorEngine()
    eng.create(PropertyEditor(
        object_type="Employee",
        name="fullName",
        title_key=True,
    ))
    with pytest.raises(PropertyEditorError) as exc:
        eng.create(PropertyEditor(
            object_type="Employee",
            name="email",
            title_key=True,
        ))
    assert exc.value.code == "TITLE_KEY_EXISTS"


def test_property_backing_duplicate():
    eng = PropertyEditorEngine()
    eng.create(PropertyEditor(
        object_type="Employee",
        name="email",
        backing_column="email_addr",
        backing_dataset="ds-emp",
    ))
    with pytest.raises(PropertyEditorError) as exc:
        eng.create(PropertyEditor(
            object_type="Contractor",
            name="contact_email",
            backing_column="email_addr",
            backing_dataset="ds-emp",
        ))
    assert exc.value.code == "BACKING_DUPLICATE"


def test_property_update():
    eng = PropertyEditorEngine()
    prop = eng.create(PropertyEditor(
        object_type="Employee",
        name="email",
        description="old",
    ))
    updated = eng.update(prop.id, {"description": "new", "indexed": True})
    assert updated.description == "new"
    assert updated.indexed is True


def test_property_promote_title_key():
    eng = PropertyEditorEngine()
    p1 = eng.create(PropertyEditor(object_type="Employee", name="name"))
    p2 = eng.create(PropertyEditor(object_type="Employee", name="email"))

    # 先设 p1 为 title key
    eng.promote_title_key(p1.id)
    assert eng.get_title_key("Employee").name == "name"

    # 提升 p2，应自动取消 p1
    eng.promote_title_key(p2.id)
    assert eng.get_title_key("Employee").name == "email"
    assert eng.get(p1.id).title_key is False


def test_property_delete():
    eng = PropertyEditorEngine()
    prop = eng.create(PropertyEditor(object_type="Employee", name="email"))
    assert eng.delete(prop.id) is True
    with pytest.raises(PropertyEditorError):
        eng.get(prop.id)


def test_property_list_filter():
    eng = PropertyEditorEngine()
    eng.create(PropertyEditor(object_type="Employee", name="a"))
    eng.create(PropertyEditor(object_type="Employee", name="b"))
    eng.create(PropertyEditor(object_type="Department", name="c"))

    assert len(eng.list(object_type="Employee")) == 2
    assert len(eng.list(object_type="Department")) == 1
    assert len(eng.list()) == 3


def test_property_not_found():
    eng = PropertyEditorEngine()
    with pytest.raises(PropertyEditorError) as exc:
        eng.get("nonexistent")
    assert exc.value.code == "NOT_FOUND"


# ── #35 Proposals 审查工作流 ──
def test_proposal_create():
    eng = ProposalEngine()
    p = eng.create("Add TSP to Sensor", "branch-001", author="alice")
    assert p.id.startswith("pp-")
    assert p.status == ProposalStatus.DRAFT
    assert p.author == "alice"
    assert p.branch_id == "branch-001"


def test_proposal_full_lifecycle():
    eng = ProposalEngine()
    p = eng.create("Update Employee schema", "br-1", author="bob")

    # DRAFT → PENDING_REVIEW
    p = eng.submit(p.id)
    assert p.status == ProposalStatus.PENDING_REVIEW
    assert p.submitted_at is not None

    # PENDING_REVIEW → IN_REVIEW
    p = eng.start_review(p.id)
    assert p.status == ProposalStatus.IN_REVIEW

    # IN_REVIEW → APPROVED
    p = eng.approve(p.id)
    assert p.status == ProposalStatus.APPROVED
    assert p.reviewed_at is not None

    # APPROVED → PUBLISHED
    p = eng.publish(p.id)
    assert p.status == ProposalStatus.PUBLISHED
    assert p.published_at is not None


def test_proposal_reject_and_resubmit():
    eng = ProposalEngine()
    p = eng.create("Fix typo", "br-2")
    eng.submit(p.id)
    eng.start_review(p.id)
    p = eng.reject(p.id)
    assert p.status == ProposalStatus.REJECTED

    # REJECTED → PENDING_REVIEW (resubmit)
    p = eng.submit(p.id)
    assert p.status == ProposalStatus.PENDING_REVIEW


def test_proposal_withdraw():
    eng = ProposalEngine()
    p = eng.create("Test", "br-3")
    p = eng.withdraw(p.id)
    assert p.status == ProposalStatus.WITHDRAWN

    # WITHDRAWN → PENDING_REVIEW (resubmit)
    p = eng.submit(p.id)
    assert p.status == ProposalStatus.PENDING_REVIEW


def test_proposal_invalid_transition():
    eng = ProposalEngine()
    p = eng.create("Test", "br-4")

    # DRAFT 不能直接 approve
    with pytest.raises(ProposalError) as exc:
        eng.approve(p.id)
    assert exc.value.code == "INVALID_TRANSITION"

    # DRAFT 不能 publish
    with pytest.raises(ProposalError):
        eng.publish(p.id)


def test_proposal_publish_requires_approved():
    eng = ProposalEngine()
    p = eng.create("Test", "br-5")
    eng.submit(p.id)
    eng.start_review(p.id)

    # IN_REVIEW 不能直接 publish
    with pytest.raises(ProposalError) as exc:
        eng.publish(p.id)
    assert exc.value.code == "INVALID_TRANSITION"


def test_proposal_comment():
    eng = ProposalEngine()
    p = eng.create("Feature X", "br-6")
    from aos_api.oma_editor import ProposalComment

    c1 = ProposalComment(author="reviewer1", body="Looks good", action="comment")
    p = eng.add_comment(p.id, c1)
    assert len(p.comments) == 1
    assert p.comments[0].body == "Looks good"

    c2 = ProposalComment(author="reviewer2", body="Need changes", action="request_changes")
    p = eng.add_comment(p.id, c2)
    assert len(p.comments) == 2


def test_proposal_add_reviewer():
    eng = ProposalEngine()
    p = eng.create("Feature Y", "br-7")
    p = eng.add_reviewer(p.id, "charlie")
    assert "charlie" in p.reviewers

    # 重复添加不报错
    p = eng.add_reviewer(p.id, "charlie")
    assert p.reviewers.count("charlie") == 1


def test_proposal_list_filter():
    eng = ProposalEngine()
    p1 = eng.create("A", "br-a")
    p2 = eng.create("B", "br-b")
    eng.submit(p2.id)

    assert len(eng.list()) == 2
    assert len(eng.list(status="draft")) == 1
    assert len(eng.list(status="pending_review")) == 1


def test_proposal_not_found():
    eng = ProposalEngine()
    with pytest.raises(ProposalError) as exc:
        eng.get("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_proposal_published_no_actions():
    eng = ProposalEngine()
    p = eng.create("Done", "br-8")
    eng.submit(p.id)
    eng.start_review(p.id)
    eng.approve(p.id)
    eng.publish(p.id)

    # PUBLISHED 不能再操作
    with pytest.raises(ProposalError):
        eng.submit(p.id)
    with pytest.raises(ProposalError):
        eng.approve(p.id)
