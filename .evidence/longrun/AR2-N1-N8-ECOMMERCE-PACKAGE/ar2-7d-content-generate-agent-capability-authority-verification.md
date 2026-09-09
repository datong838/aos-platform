# AR2-7D Content Generate Agent / Responsibility / Capability 权威验证

基线 `m1@c45a7eb7`。本段按 `ar2-7d-content-generate-agent-capability-authority-plan.md` 完成 ContentGenerate 的 AgentInstance、ResponsibilityPlan、CapabilityRevision 前置权威复验；未增加 execute/verify，未加入 readiness seal。

## 实现核对

- `ContentGenerateHostService` 在既有 Review/Handoff/Task/Brief/GrowthPlan/Artifact 输入链后，共享锁定 tenant 当前 AgentInstance 与 ResponsibilityPlan head。Agent 按 Owner 快照算法重算摘要，并只在 Host 边界映射为包侧 `AgentInstanceRevision`。
- ResponsibilityPlan 先从 public revision 原始字段按 create/revise 口径重算正文摘要，再使用 `AipProductionContractStore.get_responsibility_plan` 的动态 blockers 算法，要求 current revision/version、frozen、ready、complete、无 blocker/uncovered，并存在 Agent 当前 version 与 Capability ID 同时命中的 slot；`assignee.version: 1 -> true` 会在 DTO 归一化之前因原文摘要不符而关闭。
- Capability 使用全局 append-only 目录原始行，要求目录声明的 exact hash、published、available、无 readiness reason，且为该 capability family 最新 published revision。该 Owner 的 content_hash 本身是发布请求声明值，本段不另造目录没有定义的内容重算口径。
- ProductionContract Owner 本读取路径的五处查询显式限定 `public.`；专项 PG 在七张同名 TEMP 空表遮蔽下仍只读取 canonical public authority，随后外层 rollback。
- 实现摘要：`ecommerce_growth_runtime_adapters.py` = `5f99a3b83ab08f2c60c39238fde4cb532de78296b625382aa5ac592babb1c638`；`aip_production_contract_store.py` = `5c0b073558261030cf69fabcfd3f01389e891a24615143a51c812855886aaecc`。

## 验证结果

- 专项 Agent/Plan/Capability：`17 passed, 7 warnings in 3.27s`，含真实 PostgreSQL public/TEMP/rollback、原始 Plan `true/1` 弱类型反例和 15 类 fail-closed 漂移。
- Owner 独立回归：ProductionContract `14 passed`；Capability catalog `6 passed`；Agent registry contracts/store `14 passed`。曾把有固定 canary fixture 的多文件放入同一临时库会话，出现 2 个跨文件数据污染失败；按测试会话隔离后全部通过，不改生产逻辑。
- 扩大回归：新旧 ContentGenerate、全部 `test_ecommerce_review_*.py` 与 ProductionContract Owner 合计 `97 passed, 7 warnings in 4.08s`。
- 首次专项命令误用默认 5433，测试框架在 setup 阶段连接拒绝、零测试执行；改用既定隔离测试入口 `127.0.0.1:18434/aos_test_admin` 后通过。
- `git diff --check` 与目标 Python 编译通过。
- AR2 closure：`1707 / 91 / 57`，`hashErrors`、正反向未分类依赖、跨层 import、dynamic reference 五类数组均为空。
- memory validate：`AOS-000571 / GREEN`，Delivery Receipt `865`、event `2226`、task receipt `846`。
- 独立只读终审先发现 ResponsibilityPlan 原文摘要未闭合的阻断；补齐原始字段重算与 `true/1` 反例后复核确认阻断解除、无新增 blocker，实现摘要复核一致。

## 边界与下一项

本段不预留预算、不创建 CapabilityInvocation 或 Artifact、不读取 Secret、不调用/重试 Provider，不产生费用、审批、发布或业务副作用。动态 READY 当前按 Capability ID 判断 binding 覆盖，不证明 binding 已锁定最新具体 CapabilityRevision；该关联留给后续执行 authority 闭合。ContentGenerate 仍是 incomplete revalidate Host。下一段继续 ModelRoute、Pricing、Approval、Budget、Capacity 当前权威；230 L0 保持单独挂起。
