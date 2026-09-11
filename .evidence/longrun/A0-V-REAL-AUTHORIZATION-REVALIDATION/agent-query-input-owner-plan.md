# AgentRun 原始 Query 私有 Owner 方案

日期：2026-09-11
基线：`m1@2f53c4fc`

## 使用的 Rules

- `m1` 单写者串行；先方案再编码；只改明确文件；不 push。
- 原始 query 可能含已披露经营资料，正文不得进入通用 Artifact metadata、Receipt、日志或 Eval report。
- 租户、marking、Attempt requestHash 与 Artifact exact hash 必须同时成立；任一漂移失败关闭。
- 先建立私有、可恢复、不可变 Owner，再由后继波次接入经营参谋生成与 Eval case 派生。
- 不触发 Provider、不写真实租户、不更改现有 output retention 行为。

## 问题与目标

当前 AgentRun Attempt 只保留 requestHash，原始 query 只在调用 Provider 时短暂存在。虽然
D01/D02/D03 接收端可以根据当前 Owner 重建 query 并核对 requestHash，但正式 Eval 若要
再次从“实际发给模型的原始 query”派生来源规则，没有可授权回读的原文 Owner。

新增 `agent_query_input` 私有 Artifact 正文存储。它与 exact Artifact、Attempt、
agentRunId、requestHash、contentHash 和 marking 绑定；正文受租户 RLS、append-only
trigger 与显式 marking 控制。通用时间线只保留 hash 和引用。

## preHash 与变更文件

| 文件 | preHash |
|---|---|
| `services/aos-api/aos_api/aip_task_store.py` | `85b14bc459624cd92b770506d2c6e1dfa6bb486dca1b3a40eacc407c32090ac1` |
| `services/aos-api/aos_api/aip_agent_text_output.py` | `9ac7c9026da64ac89bcc03dfca625105e3be28e3707044f95f134362cd276be7`（参考，不修改） |
| `services/aos-api/alembic/versions/a0v_014_analyst_stage_decision.py` | `30c417b1f966fa2a90f4f15ff943e8e8348e30492948e2f8a7f0646e9f450432`（迁移父级） |
| `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md` | `1515eefecf73c60bc897cebed8e6b186e9755151544c85ebffa8fe3f76fc8f20` |

新增：

- `services/aos-api/alembic/versions/a0v_015_agent_query_input.py`
- `services/aos-api/aos_api/aip_agent_query_input.py`
- `services/aos-api/tests/test_aip_agent_query_input.py`

## 最小实现

1. 新增 `aip_agent_query_input`，主键为租户加 artifactId，Attempt 唯一，双外键绑定
   Artifact 与 AgentRunExecutionAttempt；正文、query hash、request hash、marking 不可变。
2. 新增严格 write/read helper；写入必须同时匹配 Artifact.source 中的 attemptId、
   agentRunId、requestHash，以及 Attempt Owner 的 requestHash。
3. `AipTaskStore.record_artifact` 仅在 `artifact_type=agent_query_input` 且显式提供
   `text_content` 时调用新 Owner；既有 `agent_text_output` 路径保持原行为。
4. 本波不自动保留所有模型输入；后继波次只在经营参谋受控生成路径显式写入，并将其
   exact ref 绑定到 Eval case。

## 退出条件

- 正常写读、幂等回读、租户/marking/hash/requestHash/Attempt/Artifact 类型漂移均有测试。
- 数据库更新、删除、truncate 被拒绝；正文不出现在 timeline。
- 迁移 head 为 a0v_015，相关回归和闭包检查通过；证据落盘并单独提交。
