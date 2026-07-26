"""测试组织种子：dev-org / dev-project / 默认人员。

从原 ``orgs.seed_dev_orgs`` / ``workspaces_catalog.seed_dev_workspaces`` /
``membership.seed_dev_defaults`` / ``person_identity.seed_dev_persons`` 搬迁而来。

仅在 ``demo.seed_test_org()`` 调用时执行，**不在系统启动时执行**。
"""
from __future__ import annotations

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.org_seed")


def seed_org_members() -> int:
    """灌入 dev-org 组织 + dev-project 工作区 + 默认人员（alice/bob/user:dev）。

    返回灌入的 membership 数量。
    """
    from aos_api import membership as mem
    from aos_api import orgs as org_store
    from aos_api import workspaces_catalog as ws_cat
    from aos_api.person_identity import seed_dev_persons

    org_store.seed_dev_orgs()
    ws_cat.seed_dev_workspaces()
    seed_dev_persons()
    mem.seed_dev_defaults(reset_persons=False)

    count = mem.membership_count()
    log.info(
        "seed_org_members_done orgs=%s workspaces=%s members=%s",
        org_store.org_count(),
        ws_cat.workspace_count(),
        count,
    )
    return int(count)
