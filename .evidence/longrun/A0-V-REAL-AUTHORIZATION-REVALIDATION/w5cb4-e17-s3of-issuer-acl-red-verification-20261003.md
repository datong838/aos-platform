# E17-s3o-f｜AIP 发行身份路径盘点与隔离 RED

基线 `m1@9becc509`、`AOS-001190`。只在自动新建/销毁的 `aos_test_<uuid>_ti4_test` PostgreSQL 库执行；`services/aos-api/tests/conftest.py` 用 test-only 5433 创建库、升级至代码 head `a0v_135`，测试结束 DROP。原权威库与卷未写。

| 步骤 | 命令与结果 |
|---|---|
| 上位约束 | 231-4 要求公共 Store 命令、非 owner 专用身份、租户 RLS/超时、无任意 SQL；231-9 要求 AIP 单一 Owner、Receipt-first/幂等、当前真实来源和正式三身份。|
| 原路径 | `aip_agent_registry_store.py` create/update Instance、`aip_skill_registry.py` 与 `aip_capability_binding_service.py` create/update/evaluate 均在原事务写 Registry Receipt；`aip_assignee_resolution_store.py` 同库连接写 ToolBinding/Assignee Receipt。`db.connect(scope)` 统一切到 `aos_runtime`，HTTP principal role 不构成数据库独立 issuer。|
| RED | `pytest -q tests/aip/test_e17_s3of_issuer_acl_pg.py --tb=short`：全新库迁移到135后，`with connect(TenantScope('org-org','dev-project'))` 下直接 INSERT Assignee Receipt；预期 InsufficientPrivilege，实际 `DID NOT RAISE`，exit1。事务因测试异常回滚；自动测试库销毁。|
| 待修合同 | 同一精确负例标记 strict xfail 后，与相邻 `test_w6_01_exact_assignee_resolution.py` 运行，`5 passed, 1 xfailed`，exit0。修复后 XPASS 会使测试失败，必须删 xfail 并证明实际拒绝。|
| 方案复审 | 只 REVOKE 会使原 Resolver 写同事务 Receipt 失败；独立 AIP issuer 应有独立登录/私有凭证、精确受限 DB 身份及进程边界，不能让普通 API 登录成为 issuer 成员。参考已有 Network/Budget issuer connection 的身份读回机制，绝不复用其身份或凭证。下一切片仅 Assignee Receipt，五表最终边界另续。|

本波**没有修复 ACL**，strict xfail 是显式未闭缺口；不声称正式发行、正式六绑定/八配置或首链完成。下一波 E17-s3o-g 先完成独立 Assignee issuer 最小隔离身份/ACL 方案和测试，再在 disposable PG 实现与原 Resolver 正向兼容；当前卷正式切换仍独立待办。
