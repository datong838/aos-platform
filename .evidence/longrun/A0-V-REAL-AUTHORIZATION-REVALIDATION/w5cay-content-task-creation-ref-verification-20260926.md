# W5cay｜内容 Task 创建引用与运行版本分离验证

## 第 1/6 步：复习上位方案

- 231-5 §1/§4、231-9 §2 要求 exact 方案评审后自动交接内容任务，真实能力产物经人工评审再续跑，工程师不得手补 Run。Review Handoff 原 Receipt 明示 `taskRunCreatedCount=0`；内容 Task Plan/Run 必须由后续独立 Owner 自然处理。

## 第 2/6 步：文件级清单

- 计划 `w5cay-content-taskrun-natural-owner-plan-20260926.md`，m1 `8560c73c`；追踪后修订该计划，不把 Run 偷塞进原 Handoff 事务。本波只修改 `ecommerce_growth_runtime_adapters.py` 的 ContentReview TaskRef 读回和对应单测；自然 Plan/Run Owner 顺延 W5caz。

## 第 3/6 步：RED／GREEN

- RED：Handoff/Brief/内容 Artifact 固定 Task 创建修订 1，而公共 Task 的 Plan/Run 状态推进使 `aip_task.version=4`；原 ContentReview 用当前 version 组成 TaskRef，合法内容评审误拒绝。
- GREEN：按创建修订 1 和原创建 payload/hash 核对 exact TaskRef，当前 Task row version 另要求有效；Brief/来源/目标引用不放宽。测试同时证明篡改 TaskRef hash 仍拒绝。

## 第 4/6 步：专项与累计回归

- 普通内容评审、Handoff、生成、反馈邻近 59 passed；完整测试夹具中的 Review Task/Brief PG 2 passed、Artifact PG 4 passed。7 个既有 warning。`compileall`、`git diff --check` 通过；无新迁移。

## 第 5/6 步：浏览器与一致性

- 8080 无监听，18181 仍旧 HTTP-only 诊断；没有当前真实安装/生产启动权威，本波无浏览器自然验收或 Provider 外呼。该修复只解除未来合法 Task 状态推进后的评审误拒绝，不证明 TaskRun 已自然启动或完成。
- 代码与上位一致：TaskRef 指向不可变创建内容，Task.version 属可变运行控制；原 Handoff 0 Run 合同不变。没有重发旧 12 Run、读商城源或改真实业务库。

## 第 6/6 步：下一波

- W5caz：持久 Review Receipt/current Dispatch/安装→独立幂等内容 Plan/Run Owner，需有正式可追溯审批且由原 AIP 状态机管理；再往后接 AgentRun/容量、Provider/Artifact、Step/Run 终态和 EffectReview。没有合法授权时保留 pending，不人工补引用。
