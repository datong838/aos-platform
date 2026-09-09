# AR2-7D Analysis 恢复前序 Receipt 权威验证

日期：2026-09-09
基线：`m1@65b5d822`
结论：`ANALYSIS_RECOVERY_PRIOR_RECEIPT_AUTHORITY_GREEN`

## 实现与边界

- Analysis Host 现可严格解析 START、RESUME_DATA、RECONCILE_UNKNOWN 三种既有包内命令。三者均重算完整 requestHash；exact ref 使用 canonical JSON 对账，布尔值不能冒充整数 revision。
- RESUME_DATA 限定完整 prior Receipt、Requirement、Fulfillment、Checkpoint、prior Plan、SourceReadiness、Mapping、1～200 条唯一 Evidence 及 cutoff 后 24 小时内 observedAt。RECONCILE_UNKNOWN 只接受 prior Receipt，其数据履约字段必须为空。
- runtime Store 新增租户、固定 operation 和完整 target receiptRef 绑定的 `read_exact`；重复 target、持久 target/response/requestHash 漂移均拒绝，查询显式使用 `public` schema。
- prior AnalysisRuntimeReceipt 必须为完整严格正文并重新计算 content hash；Run、Compilation、Plan、TaskRun 四类 exact ref 均逐项校验。RESUME 只接受 WAITING_DATA/WAIT_FOR_DATA，且 prior Plan、Requirement、Checkpoint 与命令相同；RECONCILE 只接受 UNKNOWN/RECONCILING + RECONCILE_RECEIPT，并保留唯一 RuntimeCommandReceipt target。
- 恢复 execute/verify 继续稳定 `analysis recovery data authority is not wired`，没有生成后继 Checkpoint 或 Runtime Receipt，也未修改 readiness seal。START 行为与重放合同保持不变。

## 验证结果

- Red：正确隔离数据库环境下，新增 exact read 与合法 RESUME 前序用例为 3 failed / 21 passed，分别失败于缺少 `read_exact` 和 Host 仍拒绝解析恢复模式。
- Green：Analysis Host、runtime Store 与包内可恢复合同聚焦 51 passed；受影响 DataFulfill、Review lineage、registry、Canonical Router、HTTP 邻接 86 passed。
- 专用 PostgreSQL runtime Store 4 passed，覆盖 exact target 正向读取与 `dev-org/dev-project` 租户 canary 不可见；使用 `127.0.0.1:18434` 一次性数据库。
- 扩展运行时全量 731 passed、471 skipped；skip 为需要显式环境开关的既有专用套件。
- Python compile、`git diff --check` 通过。
- AR2 closure：1707 scanned、91 classified、57 migrated，五类错误数组均为空。
- memory validate：`AOS-000571 / GREEN`，delivery/task/event 为 865/846/2226。
- 独立只读复审首轮指出 priorPlan 未绑定及 phase 正文校验不完整；补齐后第二轮确认无剩余 blocker。
- 一次 PG 命令漏设通用测试 fixture 的 `AOS_DATABASE_URL`，在默认 5433 setup 阶段连接拒绝、零测试执行；补齐既定 18434 隔离 DSN 后 4 passed，未改生产逻辑。

## 文件摘要

- `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：`ce57da350c7e51c112bfc14d13d5c7e0c342308cbc1389a113015b4d920e89a3`
- `services/aos-api/aos_api/ecommerce_growth_runtime_store.py`：`fa7eb3cad9cb82ee0d633139af844cc69385854c0eb382fd29f44e0df3524902`
- `services/aos-api/tests/extension_runtime/test_ecommerce_analysis_advance_host.py`：`2e658c8425d238eb629d5b46f691eed10fe4c47fe6caf6e085ce68723c1f32ec`
- `services/aos-api/tests/extension_runtime/test_ecommerce_growth_runtime_store.py`：`5ab7984c03d8fc55cafb5f4cda1ec442f652d8e5ae7e7f00888ae3cb2cfcabdf`
- `services/aos-api/tests/extension_runtime/test_ecommerce_growth_runtime_store_pg.py`：`d85106eac7ac35515b5dabe1cbd8286bae21845be5fef7094f3577f02e700d6a`

本切片没有读取真实源、调用 Provider、创建业务后继状态、发布内容、迁移生产库或写真实租户数据。下一项继续为 RESUME_DATA 接通 DataRequirement/Fulfillment/Checkpoint/Plan/Readiness/Mapping/Evidence 的真实 Owner 与后继 Checkpoint；完成后再处理 UNKNOWN target reconcile，最后才能把 Analysis 及后三项加入 readiness seal。230 L0 继续挂起。
