# E17-s3o-h｜Assignee issuer 继承收束与 Registry 直写 RED verification

基线 `m1@67cffbb2`、`AOS-001192`。上位 231-4/231-9 与本波 plan 已复习；所有角色/权限变更只在 pytest 自动创建、升级到 `a0v_135` 后删除的 test-only 数据库，当前卷只读，正式迁移仍未执行。

| 步骤 | 命令/结果 |
|---|---|
| Registry RED | `pytest -k registry_receipt_directly` 原角色：普通 runtime 与独立 Assignee issuer 都可直接 INSERT Registry Receipt，`DID NOT RAISE InsufficientPrivilege`，2 failed/exit1；写事务因断言失败回滚，随机测试库自动销毁。|
| 继承权限 RED | 隔离 issuer 对 Registry Receipt、SkillBinding、CapabilityBinding、ToolBinding 的 INSERT/UPDATE/DELETE 全为 `(True,True,True)`，预期无跨域写权失败，exit1。首次测试用 dict_row 的 `[0]` 取值导致 KeyError；改为命名列后才得到有效 RED。|
| 最小隔离修复 | test-only issuer 改为 `NOINHERIT` 且**不是** `aos_runtime` 成员；对 Resolver 实际访问的 `meta_membership`、AgentInstance/Template、Skill/Tool/Capability Binding 显式 SELECT，Assignee Receipt 仅 SELECT/INSERT；六张租户表为 issuer 单独加 org/project RLS policy。`aip_assignee_issuer_connection.py` 连接准入反向检查 runtime membership，不让广授权继承潜入。当前 Alembic head 未变，模块默认不接 API。|
| 正反复验 | 原 Resolver 使用真实隔离 membership 生成 resolved Receipt；issuer 直插 Registry 拒绝、四表 I/U/D 全 false、Assignee Receipt UPDATE/DELETE 拒绝、普通 runtime 对 Assignee 直插拒绝、跨租户 read canary 零可见、私有凭证/ACL 返宽门仍通过。普通 runtime 对 Registry 直写未修，保留 strict xfail；当前真库对 Assignee 直写未修也保留 strict xfail。|
| 相邻回归 | `pytest -q tests/aip/test_e17_s3of_issuer_acl_pg.py tests/aip/test_w6_01_exact_assignee_resolution.py tests/aip/test_w_l20_assignee_resolution.py --tb=short` → exit0，13 passed/2 xfailed/7 warnings；`py_compile` exit0，test-only issuer 角色剩余0；当前签名预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、API health200。|

方案复审：这只是测试库的最小权姿态与默认关闭的连接器；已正向验证 Human assignee，Agent/Tool/Provider 三类真实 issuer 读路径尚需各自完整正向/负向。普通 runtime 的 Registry/Skill/Capability/Tool 表权限仍过宽，当前真实库 Assignee ACL 也未变；后续需在隔离克隆做原 Registry/Binding 命令同事务正向和正式迁移，再以新备份/克隆全链/零执行窗口切换当前。Host/worker/Provider、正式六 Binding/八配置/自然首链继续禁入。

代码提交后用原签名制品预检，`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、代码/库头135、runtimeBindings0；独立备份 SHA仍为 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0`。仅重载原 launchd API 到 PID41852，健康/就绪/OpenAPI/Web200，PG18435/Web8434继续、18181无监听。此为代码局部重载，不是新的完整 PG/API/Web 重启验收。
