# W5cas｜隔离 PG 内容消费/状态真链核验

## 范围与方案一致性

依据同目录 `w5cas-content-consumer-isolated-pg-plan-20260926.md`、231-5/6、W5car verification。基线 m1 `85315f44`，计划提交 `8887bc8c`。本波只修测试夹具：原两组测试从不存在的 `public.aip_lineage_event`/`aip_artifact` 复制表，空隔离 PG 在夹具阶段失败。新 `tests/aip/content_consumer_pg_baseline.py` 在每例随机 schema 按 AIP-1/AIP-4 与后续字段/约束的必要子集建立 Lineage/Artifact 和租户 RLS；不改生产 Owner、预算或授权策略，不把测试局部表宣称为完整公共迁移。

## 真事务核验

原 9 项 Consumer/Usage PG 由夹具失败转为 **9 passed**。在原 Worker mock Provider 单次返回测量值→不可变 Journal→原 Consumer 的事务内 Usage、Lineage、可读 Artifact、Budget 结算后，新独立 Reader 实际 SQL 回读 `COMPLETED` 或 `COST_PENDING`；注入结算失败时 Usage/Artifact/Lineage 均回滚，状态保持 `RESULT_RECORDED_UNSETTLED`。隔离测试再由 owner 删除 Artifact，Reader 拒绝完成；`dev-org/dev-project` 只读查询拒绝。测试模拟 Provider 响应，不是真实外部调用或业务成果。

9 个相邻文件合计 **87 passed、7 既有 warnings**；测试 helper 编译和 `git diff --check` 通过。无 UI/路由变动，浏览器 N/A。临时 `aos-w5car-regression-pg` 只映射 127.0.0.1:18432，测试后已精确停止；无商城源数据读取或旧 Run 重播。

## 未完成与下波

该夹具只覆盖本链所需表，不等于全量生产迁移验收。`AOS_ECOM_CONTENT_WORKER_ENABLED` 仍默认关闭，当前真实安装/事实新鲜度/审批/费用与出境/Provider/TaskRun 未核，因此无自然内容产物、人工评审或业务闭环。旧 12 Run 正式退休及 230 L0 后置，dev-org 保持零 canary。

W5cat：先复习 231-2/3/5/6 与当前已签名候选包，写新版本包的精确清单和安装迁移/旧代次围栏方案；实现最小变更、签名验收与当前 scoped authority 只读 canary。任何一个门不全都不开真实 Provider，继续可并行的人工评审续跑研发。
