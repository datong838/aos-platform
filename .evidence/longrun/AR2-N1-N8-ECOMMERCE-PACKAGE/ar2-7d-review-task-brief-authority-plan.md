# AR2-7D ReviewAdvance 内部 Task/Brief 权威

基线 `m1@a0153331`。Rules：m1 独占串行、方案先行、最小更改、Red-Green、逐步留证并提交；不 push，230 L0 挂起。

## 当前缺口

`ReviewAdvanceHostService._review_lineage()` 固定抛错；现有测试以 monkeypatch 返回 Handoff/Task/Brief，未证明生产 Owner。231-6 要求 ACCEPT 在宿主事务内形成唯一 Handoff、内部 Task 和 TaskBrief，并保持外部副作用为零。

## 修改范围

- 维护 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：
  - 以 Review 命令正文生成确定性 `HandoffReceipt` exact ref；该子回执随完整 Review response 写入现有不可变 `ecommerce_growth_runtime_command_receipt`，后续仍由完整 Receipt 回读校验。
  - 复用 `AipTaskStore(TransactionBoundConnectFactory)` 创建 `ecommerce.workshop.business_task`，稳定 key 为 Review key 的命名子键；Task 使用中文业务标题/目标及固定“活动策划师 requested”分配，并保留 Handoff、GrowthPlan、四 Artifact 来源。
  - 复用 `AipProductionContractStore(TransactionBoundConnectFactory)` 创建 `content_campaign` TaskBrief；使用现有 ContentCampaign schema ref，spec 明确保留 Handoff、Task、GrowthPlan、四 Artifact、渠道、受众、时间窗、约束及 `externalPublicationRequested=false`。
  - 从实际 `aip_task` 请求摘要和 TaskBrief revision 内容摘要构造 exact refs；任何 Owner 重放漂移均 fail-closed。所有 store commit 由 transaction-bound wrapper 吞掉，最终提交权仍只属于 HostPort。
  - 所有嵌套 GrowthPlan/Artifact exact refs 重新经过严格 DTO 校验，拒绝 Python `bool == int` 等弱相等绕过；中文业务字段必须已去首尾空白、无格式控制字符且为 NFKC 规范形。
  - 创建后直接回读 `public.aip_task`、`public.aip_task_brief_head`、`public.aip_task_brief_revision` 与 `public.aip_production_contract_receipt`，按 Owner 原算法重建请求/内容摘要并逐字段核对；不把 Store 返回 DTO 或任意 64 位字符串单独当作权威。
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_review_task_brief_authority_pg.py`：真实18434隔离库验证单事务创建、稳定重放、内容漂移、租户隔离及外层 rollback。
- 维护 `test_ecommerce_review_advance_host.py`，删除对 `_review_lineage` 的假成功依赖，或将其保留为纯 Receipt 单测并由 PG 专项覆盖生产 lineage。

## 边界

本切片不调用 Provider、不创建 TaskRun、不发布、不写真实租户数据；Handoff 不签发 token。GrowthPlan 当前性、ReviewIssue/Eval/Artifact/Analysis exact lineage 尚未全部回读，ReviewAdvance 不加入 readiness seal。后续先补齐这些输入权威，再声称该 operation 完整。

## 验证

先用生产 `_review_lineage` PG 测试确认旧固定拒绝；修复后运行新增 PG、Review/Analysis/runtime registry/Task/Brief 邻接，验证 HostTransaction 外层回滚、嵌套布尔 revision 拒绝、public Owner 正文/摘要闭合和跨租户不可见；再跑闭包、memory validate、diff check及本地独立复核。
