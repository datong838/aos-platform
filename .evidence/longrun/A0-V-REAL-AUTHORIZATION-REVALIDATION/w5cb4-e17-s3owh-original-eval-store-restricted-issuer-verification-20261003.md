# W5CB4 E17-s3o-w-h｜原 EvalContract Store 受限发行首个正向切片

基线 `m1@2e8898da`、Authority `AOS-001216`；先复习 231-3/4/5/9、栖月汇方案及本波文件级 plan。唯一改动代码文件为 `services/aos-api/tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py`，无生产 Store/迁移/UI 变更。专用 `aos-ar1c-pg:18432` 内一次性数据库 `s3owh_*`，只装原 `aip4_002` EvalSuite、`w2_002` EvalContract 和 `w2_001` Receipt 表形状；测试结束只清理本次创建的数据库/登录。未连当前权威卷做 DML。

| 检查 | 本轮输出 |
|---|---|
| RED 与隔离路径修正 | 原双身份协议的第三合同登录调用真实 `AipProductionContractStore.create_eval_contract`，在 `aip_eval_suite_revision` SELECT 处因权限不足失败，exit1。代码又显式读取 `public.aip_eval_contract_head/revision`，临时 schema 无法覆盖重放；先更新方案，再改用专用测试容器的一次性独立数据库 public schema，而不是修改原 Store 或绕过读回。 |
| 独立发行身份与原方法 | `s3owh_contract_*` 真实 LOGIN/NOINHERIT、非 owner/NOBYPASSRLS 直接连接一次性数据库，session/current_user 精确同一角色。只授 suite SELECT、Eval head SELECT/INSERT/UPDATE、revision SELECT/INSERT、共享 Receipt SELECT/INSERT；三表 runtime 写权限撤销，租户 RLS 强制。测试触发器要求 session+租户+`eval_contract.create/revise/freeze`，Receipt 的 `result_ref` 对应同租户 current head/revision/hash；数据库角色与触发器均只在测试库。原 Store `create_eval_contract` 写出 head/revision/Receipt 一组，回读 READY 为 BLOCKED（缺正式 publication/gate），不是可运行配置。 |
| 幂等/拒绝/回滚 | 原方法同键同输入回读同一 contractId；同键改输入抛 `ProductionContractIdempotencyConflict`，配对结果仅1组。合同登录跨租户 head INSERT 被拒；缺配套 head/revision 的 Receipt 被拒。测试触发器对 `forced-rollback` 注入错误，原方法事务失败后 head/revision 计数均不增、该键 Receipt0。此处注入仅测试事务原子性，不当作正式来源或外部副作用。 |
| 专项与相邻 | 专项 `AOS_EXTENSION_PG_TEST=1 .venv/bin/pytest -q tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py`：7 passed，exit0；完整相邻四文件（同协议、原权限 RED、只读锁、当前配置来源）`30 passed/9 strict xfailed`，exit0。加最后 revision 零增量断言后，原 Store 单测 1 passed，exit0。`compileall` 与 `git diff --check` exit0，生产代码和迁移差异为空。 |
| 清理与当前库 | 独立测试 PG 只读目录查询 `s3owh_*` 数据库、`s3owh_contract_*` 角色各0，exit0；当前权威 `aos_current_preview_20260927` 只读仍 `a0v_135`，正租户共享 Receipt0，exit0。 |

复审：原 Store 方法和原表形状/受限 DB 登录在此隔离切片相容，配对与幂等/回滚获直接证据；该测试 suite 是隔离生成的合法形状数据，**不是当前正式 EvalSuite、发布门或审批来源**。其余29个固定操作、Plan generic/BI、successor、内容注册、原只读 reader `FOR SHARE`、正式三身份/Owner、当前八配置与自然首链均未获完整正向。此测试触发器和角色不能直接部署；生产权限迁移与当前卷切换必须单独设计并经备份/克隆全链/零执行窗口。当前真实库只读、Host/worker/Provider关闭，Goal active、不 push。浏览器不适用于纯隔离 DB 测试，沿上一波当前页面禁入事实，不以此测试替代浏览器业务验收。
