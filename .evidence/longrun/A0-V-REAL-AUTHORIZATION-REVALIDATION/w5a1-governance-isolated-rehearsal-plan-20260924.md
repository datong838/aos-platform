# W5a1 治理最小隔离演练方案（2026-09-24）

## 权威与目标

W5a 已在 `b8bcfb35` 冻结同一 `planHash=41813b34c4ce092d3bddd81115169ac52ca1b644819e57e5b29e801fb27a1265`，主库未发布。上位 `formal-text-model-plan.md`、W5a 计划与部分验收要求：先独立当前态演练和主库保全，才能考虑一次正式 apply。此波只补齐这两个门禁，不运行 W5、DS、definition 或商城任务。

## 最小范围与文件

- 只读盘点 `pg_catalog`、现行治理 Owner 的精确 tenant 行及 FK；不得读取、导出、备份商城源表、订单、对象或客户数据。`org-org/dev-project` 是唯一正向租户，`dev-org/dev-project` 仅检查零 canary。
- 拟新增 `scripts/a0v_w5a_governance_clone.py` 与相应 `services/aos-api/tests/test_a0v_w5a_governance_clone.py`；必要时对 `scripts/a0v_formal_text_model_renewal.py` 的数据库白名单做仅允许固定演练库的最小改动。实施前先证明表闭包、所需行、角色/RLS/触发器/迁移头都可不依赖商城内容而复现；否则不编码、不建库。
- 演练库固定为 `aos_w5a_governance_20260924`，只含 schema 与精确治理依赖行，不含任何 ecommerce/pipeline 源行。生成物放于私有 0700 目录，内容文件 0600；仓库仅保存去敏计数、hash 和结论。

## 串行门禁

1. 盘点正式发布函数的读写表、精确引用、FK 与现库修订头；核对 m1 干净、8080 健康、W5a 计划未过期且主库未推进。若任何闭包未知，冻结。
2. 制作 schema-only 隔离库及精确白名单治理行导入器，拒绝 `ecommerce_*`、`pipeline_*`、非正向租户与任意全表数据导出；在测试中证明拒绝路径。数据库创建若失败，不重试未知结果，先只读对账。
3. 克隆后比较 Owner head/revision 的精确 hash、CAS version、迁移头、RLS/触发器/角色；确认商城数据表为空、canary 无正向授权。不能证明则不演练。
4. 在隔离库使用 W5a **同一个**计划/证据，只执行一次 apply；独立回读 Budget/Price/Policy/Model/Route 双 EvalGate 和业务零副作用，检查 Owner 回执。未知写入结果不换计划、不重复调用。
5. 主库保全采用仅治理依赖表/行的独立、可校验快照，先核对不含商城内容与可恢复性；若该保全不足以覆盖 apply 可能变动的全部表，则 W5a 正式库仍冻结。
6. 写 verification 并提交 m1，不 push。若演练与保全双绿，下一波才可按 W5a 原方案考虑主库一次 apply；否则转入具体根因修复波。

## 停止条件

任何数据范围、数据库身份、提交边界、Owner 回执、计划有效窗或租户隔离不明即停止本波的写入；不能以测试绿、旧克隆或全库备份替代。无人工 `run_definition`，不重打三次 Provider 固定评测。
