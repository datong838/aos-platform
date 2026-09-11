# 可读增长计划草稿接收方案

基线0f588e38，持续全权本地开发、m1串行、不push、230 L0挂起。沿231-5/231-6和既有Analyst GrowthPlan Owner，先实现独立受信服务，不提供绕过安装/角色/预算的公开接口。

## 数据与可信边界

1. 已有DecisionSummaryRevision/InsightRevision和EvidenceBundleRevision提供事实摘要、exact来源及不确定性。具体PostgreSQL读取器以当前tenant查询，核对payload哈希、current head、证据发布/撤销/时效和marking；缺任何依赖则拒绝。没有来源时不生成默认事实。
2. 固定版本提示词由已核对的Decision与来源元信息、明确配置的计划预算生成，计划预算不能从模型答复取得，也不能用0掩盖未知。它与本次开发大模型费用授权不是同一概念。
3. 结果接收前读取原AgentRun及SUCCEEDED执行attempt，核对它确实使用D03、声明相同decision/evidence输入。按原ExecuteAgentRunRequest字段重算固定提示词请求hash，拒绝演示prompt/其他请求；答复SHA256必须等于原outputArtifactRef及已落库Artifact，Unknown/failed无结果拒绝且不重发Provider。
4. 答复采用有界严格JSON，拒绝重复字段、额外字段、非有限数字、空白/空壳内容、未知来源索引。模型只填写目标、预期作用、信心、不确定性相关约束、停止条件和有来源的行动建议；不能填写tenant/revision/hash/lifecycle/approvedAt/budget或执行许可。
5. 复用GrowthPlanRevision：补可选逐项EvidenceBundle exact列表和生成Artifact exact引用，旧对象不携带新增空字段以保持旧序列化/hash。新草稿由服务器填写draft、版本1、稳定标识、原完成时间、明确预算及decisionRef；所有模型条目来源必须包含于核验来源。由现有Owner保存可读正文及Receipt，随后人工审批仍走原服务。
6. 单个受信接收事务先读并核对来源/attempt/Artifact，再通过同连接的现有Owner最后提交，失败回滚。相同attempt/请求生成同一plan/key；相同key不同内容或actor拒绝，已经生成可回读不重复建草稿。来源撤销与草稿保存的并发窗口不等于执行许可，审批/执行必须继续重验当前来源；该重验接线列为后续闭环验收项。

## 文件和验证

- services/aos-api/aos_api/ecommerce_analyst_growth_plan_draft.py：严格答复结构、固定提示词、来源/生成证据检查及草稿接收服务。
- services/aos-api/aos_api/ecommerce_analyst_authority_contracts.py：可选来源/生成引用与旧payload序列化兼容。
- services/aos-api/tests/test_ecommerce_analyst_growth_plan_draft.py及既有contracts/approval/store测试：有效草稿、假审批字段、错来源/租户/答复hash/请求hash、缺失/Unknown、重复和漂移、预算非模型控制、旧hash保持。
- 完整隔离克隆验证真实Owner保存与重放，测试数据只在自有隔离scope/schema；不在栖月汇真实业务中造fixture。待真实数据、技能绑定和安装具备后，再接实际模型请求与页面草稿展示。

本波不能声称已生成真实栖月汇计划；独立服务完成也不代表调用点和UI已经接线。后续仍包括审批当前来源重验、模型答复持久接收/未知恢复、真实入口与自然事件、内容续跑、八场景和观察发布。

## 串行检查点（2026-09-11）

为保证每次提交可独立回归，先提交步骤4/5的答复解析与可选来源契约：无数据库写入、无Provider调用、无公开入口。步骤1/2/3/6（当前来源读取、固定prompt、原attempt核验、Owner保存与克隆重放）接续施工，不能将本检查点视为接收服务完成。新增契约对旧payload省略空字段，针对既有contracts/store/approval回归；下一检查点需补新来源字段穿过审批的验证。
