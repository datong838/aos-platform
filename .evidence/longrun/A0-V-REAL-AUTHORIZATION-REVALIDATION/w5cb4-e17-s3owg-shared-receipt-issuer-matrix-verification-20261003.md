# W5CB4 E17-s3o-w-g｜共享 Receipt 操作与发行身份隔离矩阵

基线 `m1@a394def7`、Authority `AOS-001215`；方案见同波 `...s3owg-shared-receipt-writers-plan-20261003.md`。先读 231-3/4/5/9、栖月汇方案、原 Store 与 `w2_001/w2_002`、上波 SQL 协议和 RED；仅在独立 `aos-ar1c-pg:18432` 的一次性 schema 扩展测试，没有生产 migration 或当前库 DML。

## 文件级事实与 RED/GREEN

- 原应用写入点：`aip_production_contract_store.py` 有 `_receipt` 33 个调用（30固定字面量、3动态 Plan）；Plan 创建/修订/冻结当前只接受 generic/BI 六种 operation。`aip_content_draft_store.py` 另直接 INSERT `content_draft.register`。因此审计中的标签候选为37种；`aip_responsibility_assignment_store.py` successor 写 Plan head/revision 和自己的 successor 表，**不**写共享 Receipt。迁移 `w2_001` Receipt 唯一键按租户+operation+幂等键，原 runtime 仅撤销 UPDATE；`w2_002` Plan head 可变、revision append-only。
- 文件只改 `services/aos-api/tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py`：保留 Plan、Content 非 owner/NOINHERIT 测试登录，新增独立 ProductionContract 登录；将原 `LIKE` Plan operation 映射收紧为六个精确名字，并列出30个原 Store 字面量。AST 检查原 Store 固定调用双向等于30项，变更时可失败提醒名单漂移。
- RED：新独立合同发行者对原 `_receipt('eval_contract.create')` 原 SQL 形状写入，旧 trigger 返回 `RECEIPT_OPERATION_UNMAPPED`（SQLSTATE42501），专项 `1 failed/1 passed`，exit1。GREEN：给第三身份独立 SELECT/INSERT 与租户 RLS，仅30个名单操作可通过；Plan六项和内容一项仍走各自身份，未知操作拒绝。专项 `6 passed`，exit0。单测试循环37个标签写入，runtime 直写、跨身份、未知标签、跨租户及合同身份写 Plan head 均被拒；原同键只读锁试验仍通过。
- 相邻 `AOS_EXTENSION_PG_TEST=1 services/aos-api/.venv/bin/pytest -q services/aos-api/tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py services/aos-api/tests/extension_runtime/test_plan_receipt_issuer_red_pg.py services/aos-api/tests/extension_runtime/test_plan_readonly_lock_protocol_pg.py services/aos-api/tests/extension_runtime/test_current_configuration_sources_pg.py --tb=short --disable-warnings --log-cli-level=ERROR`：exit0，`29 passed/9 strict xfailed`。原9 xfail 仍是当前宽权限/原读者锁的未修复事实，不能混为通过。`compileall`、`git diff --check` exit0。
- 隔离 PG 只读查 `pg_roles`：`s3owg_contract_%` 与 `s3owe_%` 残留均0，exit0。当前权威 `aos_current_preview_20260927` 只读查仍为 `a0v_135`，正租户共享 Receipt 计数0，exit0。未触发 API/Web/Host 变更，浏览器验收不适用于这个测试协议切片。

## 复审、限度与下一步

这仅证明**标签到三类测试数据库身份的 SQL 路由**，不是37个原生产者的完整正向。矩阵测试复用 `_receipt` 写入形状，非 Plan 标签的批量行未逐一证明业务 `result_ref`、配套 head/revision/产物或前置审批真实有效；第三身份持有 INSERT 时仍可能直接伪造同类标签的任意 Receipt。不能部署该测试 trigger、提升为正式账号、宣称安全发行或业务首链 GREEN。原 generic/BI/successor/content 的受限连接、结果关联、幂等/CAS/失败回滚与现有 reader `FOR SHARE` 兼容仍待独立隔离链；正式 issuer/ACL 迁移和当前库切换须新一致备份、克隆全链及零执行窗口。当前库只读、Host/worker/Provider关闭，Goal 继续 active，不 push。
