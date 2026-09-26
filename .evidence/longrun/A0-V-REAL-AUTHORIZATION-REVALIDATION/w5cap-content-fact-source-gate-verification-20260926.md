# W5cap｜内容生成 v2 事实来源门核验

方案：`w5cap-content-fact-source-gate-plan-20260926.md`。上位为 231 A1、231-5、231-6 AR2-6/N7、231-9 BG-04 与栖月汇双侧增长产品方案。当前 m1 前置 `f03fafc9`；只改 `ecommerce_growth_runtime_adapters.py` 和内容生成 Handoff 测试，旧用户未跟踪文件未动。

## 第 1–4/5 步证据

- RED：新增 v2 来源权威/拒绝/重验前阻断测试，首次专项 2 failed、15 passed，缺 `_fact_source_authority`；实现后专项 18 passed。
- GREEN：含批准 `salesWeaponMethod` 的 v2 内容生成命令在原 HostTransaction、预算 hold 之前，要求 `factSourceRefs` 与方法的 EvidenceBundle exact refs 逐项同版；使用原 `require_growth_plan_sources` 以 `internal` marking、DB checked_at、七天界重读当前 Decision→Insight→EvidenceBundle/底层 Evidence，核方法来源是 Decision 子集，Insight cutoff 与批准方法相同。过期、撤销、缺项、hash 替换和额外履行 Receipt 均拒绝。旧 v1/no-effect 路径不变。
- 累计：相邻内容生成/Review/合同/来源 12 文件 **195 passed、7 既有 warnings**；两项隔离 PG Review/TaskBrief **5 passed、7 既有 warnings**；`compileall`、`git diff --check` 通过。无新 UI，浏览器 N/A。隔离 PG 测试验证的是已有 Plan/Brief Owner，本波来源门使用已有来源 reader 并有单元和 Host 调用路径测试；**尚无真实租户自然 v2 请求验收**。

## 方案/代码一致性、风险与下一波

符合先证据再能力原则：本波没有更改 `execute` 的无效果释放，也没有入队、调用 Provider、写真实租户、读取商城源或对外发布。方法证据权威不等于商品语义正确或业务建议有效；额外 Dataset/履行 Receipt 暂拒绝，等同源闭包可证后再扩。现有 `ContentExecutionJournal`、`ContentExecutionWorker`、`ContentResultConsumer`、`ExactProviderInvoker` 已有隔离实现，但没有接进当前 Host；不能重造第二套 Owner 或把独立测试结果当实链。

下一波 W5caq：先复习上述原 Owner、A1/AR2-6 状态与 Provider/Approval/安装门，写文件级计划；在不自动外呼的前提下，打通当前 Host 的 held Reservation→持久 Journal 命令及 exact 回读；然后做唯一 worker 的权威 prepare、提交后调用、结果消费和 UNKNOWN 只读对账。真实 Provider 调用仍须当前 scoped 费用/出境/模型审批、健康与可用业务事实；缺一项只挡该实例，继续其他主线。旧 12 Run 后置，230 L0 挂起，dev-org 零 canary，m1 单写不 push。
