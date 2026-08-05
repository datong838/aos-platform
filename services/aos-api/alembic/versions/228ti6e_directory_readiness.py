"""TI-6 3A align the test and Qiyue control-plane directory.

Revision ID: 228ti6edirectory
Revises: 228ti6drelations
Create Date: 2026-08-05
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti6edirectory"
down_revision: str | Sequence[str] | None = "228ti6drelations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE meta_org SET name='测试组织' "
        "WHERE id='dev-org' AND name='默认组织'"
    )
    op.execute(
        "UPDATE twa_org SET name='测试组织' "
        "WHERE id='dev-org' AND name='默认组织'"
    )
    op.execute(
        "INSERT INTO twa_org (id,name,kind,join_policy,discoverable) "
        "VALUES ('org-org','栖月汇商贸有限公司','standard','invite_or_apply',false) "
        "ON CONFLICT (id) DO NOTHING"
    )
    op.execute(
        "INSERT INTO twa_workspace (org_id,project_id,name,deletable,kind) "
        "VALUES ('org-org','dev-project','默认工作区',true,'default') "
        "ON CONFLICT (org_id,project_id) DO NOTHING"
    )


def downgrade() -> None:
    # Remove only the exact control-plane seed while it still has no tenant
    # activity.  Any later member/invite/audit relation makes downgrade fail
    # closed by retaining the authoritative directory rows.
    op.execute(
        "DELETE FROM twa_workspace w WHERE w.org_id='org-org' "
        "AND w.project_id='dev-project' AND w.name='默认工作区' "
        "AND NOT EXISTS (SELECT 1 FROM twa_ws_member m "
        "WHERE m.org_id=w.org_id AND m.project_id=w.project_id) "
        "AND NOT EXISTS (SELECT 1 FROM twa_invite i "
        "WHERE i.org_id=w.org_id AND i.project_id=w.project_id) "
        "AND NOT EXISTS (SELECT 1 FROM twa_join_request j "
        "WHERE j.org_id=w.org_id AND j.project_id=w.project_id) "
        "AND NOT EXISTS (SELECT 1 FROM twa_audit a "
        "WHERE a.org_id=w.org_id AND a.project_id=w.project_id)"
    )
    op.execute(
        "DELETE FROM twa_org o WHERE o.id='org-org' "
        "AND o.name='栖月汇商贸有限公司' "
        "AND NOT EXISTS (SELECT 1 FROM twa_workspace w WHERE w.org_id=o.id)"
    )
    op.execute(
        "UPDATE meta_org SET name='默认组织' "
        "WHERE id='dev-org' AND name='测试组织'"
    )
    op.execute(
        "UPDATE twa_org SET name='默认组织' "
        "WHERE id='dev-org' AND name='测试组织'"
    )
