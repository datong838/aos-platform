# 阶段评审 Eval/source proof reader 施工方案

日期：2026-09-12

基线：`0ebb9f20`

## 目标

把 `ecommerce_analyst_stage_review_command._sources_and_eval` 拆成纯数据库 proof reader 与旧同步兼容包装。新 reader 在事务一内核验 subject/parent、Artifact、ExecutionAttempt、AgentRun、原 query、当前 EvalContract/Suite、ReleaseGate 和最新 EvalReport，但不调用 Growth 包；它输出 `validate_eval_proof` 和 `validate_structure_case` 两条 exact 消息。

## Rules

1. 原 query 只能来自同 attempt/agentRun/requestHash 的唯一 `agent_query_input` Artifact，并继续经过 markings reader。
2. structure 消息 expected hash 只能来自当前 Eval Suite 唯一 required positive case 的 input Artifact content hash。
3. Eval proof 必须来自现有 `read_stage_eval_report` 返回的 passed/latest report，并绑定同 tenant、artifact、attempt、contract、policy、cutoff 与事务时钟。
4. snapshot 固定 generation Artifact/Attempt/Agent、Skill/route/policy、query Artifact、contract/suite/gate/report exact refs 与关键时间/hash；第二事务重读任一漂移即拒绝。
5. 旧同步 service 仍可注入 `derive_structure_case` 并原位比较；新 reader 传空 deriver 时只生成 proof，禁止在事务内包调用。
6. 不接产品入口、不改 Installation、不写真实数据；完成 reader 后再组合五门并接 Owner 双事务。

## 验收

- 现有 source/eval 23 类漂移测试全部保持；新增 proof 的 snapshot/payload/expected 均 canonical JSON。
- structure hash 与 Suite case input exact 一致，Eval payload 可由作者包规则接受。
- 未提供 deriver 的新 reader 调用计数为零；旧同步路径 deriver 调用一次。

## 下一步

先提取返回结构并补齐测试，再实现五门 composite reader、Owner replay fast path 和产品级异步 command service。
