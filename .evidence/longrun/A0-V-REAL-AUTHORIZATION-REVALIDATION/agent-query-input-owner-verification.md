# AgentRun 原始 Query 私有 Owner 验证

2026-09-11，基线 `m1@2f53c4fc`。

新增 `aip_agent_query_input` 前向迁移和私有读写 Owner。数据库同时约束 tenant、Artifact、
Attempt、query contentHash、execution requestHash、marking 与唯一 attemptId；正文最长
16,000 字符且不超过 2 MiB。表启用 FORCE RLS，并拒绝 update、delete、truncate。

`AipTaskStore.record_artifact` 只为 `agent_query_input` 和既有 `agent_text_output` 接受私有
正文。query 写入时必须匹配 Artifact.source 的 agentRunId/attemptId/requestHash 以及
Attempt Owner 的 requestHash；通用 Artifact metadata 只保存引用、hash 和长度。

专项、既有输出留存与 AgentRun executor 联合回归为 `73 passed / 1 skipped`，4.60 秒；
pytest session 启动时实际迁移到新 head，`alembic heads` 为 `a0v_015 (head)`。skip 是既有
需显式完整图开关的输出正文数据库专项，不影响本波实际 migration setup。三个 Python
文件编译通过。

本波只建立可授权回读、可恢复且不可变的原始 query Owner，没有默认留存所有模型输入，
也没有调用 Provider。下一波由经营参谋 D01/D02/D03 受控生成显式写入该 Owner，并把
exact query Artifact 交给 Eval case 派生。
