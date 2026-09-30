# W5CB4 BG00cs｜私有签发接口只读 Inquiry 验证

- 基线：m1 `371f878b`、AOS-000948；任务 Receipt `W5CB4-BG00CS-20260930`。方案 `w5cb4-bg00cs-private-issuer-inquiry-plan-20260930.md`。
- RED：`AOS_TEST_USE_SHARED_DATABASE=1 services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_network_issuer_service.py` 退出1，缺模块 3 failed/1 skipped。
- GREEN：`AOS_TEST_USE_SHARED_DATABASE=1 AOS_BG00CQ_PROOF_DIR=/Users/ddt/work/projects/ai_agent/.aos-bg00cm-issuer-qTLrIa services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_network_issuer_service.py services/aos-api/tests/aip/test_aip_network_issuer_reconcile.py services/aos-api/tests/aip/test_aip_network_issuer_auth.py services/aos-api/tests/aip/test_aip_network_issuer_contracts.py` 退出0，29 passed。`compileall -q` 和 `git diff --check` 退出0。
- 克隆证据：只在 test-only `aos-bg00ck-isolated-pg` 以独立 issuer LOGIN + transaction runtime role、只读连接查询，Event0 返回 UNRESOLVED。该测试的 Principal 用受控替身，故只证明组合和数据库权限，不证明正式 JWT/IdP。
- 方案/代码复审：Inquiry 先 BG00cr 外部身份校验再开显式只读连接，expected actor 只取签名 principal；BG00cq 核对 DB、角色、事务租户、网络 Proposal/Event。DecisionCommand 在任何认证/连接前拒绝 `ISSUER_ATTEMPT_RECEIPT_REQUIRED`；无自动重发分支。未新增路由、进程、数据库表或迁移，未碰当前库。
- 未完成与风险：任务最初期望的私有 IPC/进程及 bounded decide 未交付；缺持久 attempt Receipt 时 UNRESOLVED 无法证明安全重试。正式外部 IdP、OS 身份、HBA、当前第二 checker 及首链仍缺。下波 BG00ct 先设计并验证 attempt 持久化和单次消费，再做进程/IPC。
