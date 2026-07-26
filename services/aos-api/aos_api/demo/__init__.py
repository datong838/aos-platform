"""测试组织数据种子包。

所有开发/测试/回归验证用的演示数据统一存放在这里。
所有种子函数只操作 ``org_id='dev-org'``、``project_id='dev-project'`` 的数据，
和企业线上组织数据物理隔离。

调用入口：

    from aos_api.demo import seed_test_org, clear_test_org

    seed_test_org()   # 灌入测试组织 + 工作区 + 业务数据
    clear_test_org()  # 清空测试组织数据（回归清理用）

设计原则：
    - 系统启动**不**自动灌测试数据（main.py 只调用 ``ensure_system_meta``）；
    - 所有 HTTP 接口/业务逻辑和线上一致，没有 mock fallback；
    - 测试数据仅通过显式脚本注入或清理，方便开发/测试/回归。
"""
from __future__ import annotations

from aos_api.demo.seed import clear_test_org, seed_test_org

__all__ = ["seed_test_org", "clear_test_org"]
