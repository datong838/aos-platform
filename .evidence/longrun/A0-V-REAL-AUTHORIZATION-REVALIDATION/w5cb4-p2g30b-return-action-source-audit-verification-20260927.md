# W5CB4 P2g30b RETURN Action 来源追溯与安全停止核验（2026-09-27）

## 本切片结论

- 以当前隔离集成 RED 复现：`test_original_settled_artifact_runs_current_content_subject_eval[RETURN]` 在公共 `AipActionStore.create_proposal` 之前被 `REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED` 拒绝。原 Task/Run running、唯一 queued 后继、正式 ReturnDecision、原 Artifact、revise/freeze Brief 已在前段读回；尚无新 Action 提案/批准，因此未授权能力调用。
- 追踪正式来源图：`ContentResultConsumer` 将 `aip_artifact.source.invocationId/providerResultHash` 连到预算 reservation；`ContentExecutionJournal.read` 可用 reservation 找原 command/result；原 command 携 AgentInstance、ResponsibilityPlan、Capability 等 exact refs。消费端 `require_repair_approval_binding` 已要求新批准与六项 payload/安装代次完全一致。
- 做过一次**未提交**的正向接线探针；该探针在调用既有 `_agent_capability_authority` 时，明确失败于 `content generate AgentInstance authority is missing`。原因是当前隔离原命令来自 `tests/aip/test_aip_budget_reservation_pg.py::content_generate_command`，其 Agent/计划/Capability 引用是合成占位，原受控测试并未创建正式当前 Owner 记录。这是测试来源缺口，不证明可以删除生产权限门。
- 已用 `apply_patch` 将该探针的两个生产模块精确恢复到原 fail-closed 内容，`git diff` 对两文件为零；负向四项测试通过。保留未提交的正向 RED 测试供下一切片使用，未让不受证明的 Action 写入 m1。

## 下一切片

- 先在隔离集成库用正式 AgentRegistry、ResponsibilityPlan、Capability Owners 建立当前完整来源，并重算原命令 exact refs；本切片 RED 应先走过当前能力校验，再验证当前 dispatch、ActionType、maker/checker、事件和重放。不得靠 monkeypatch `_agent_capability_authority`、伪造 UI 绿或删除校验。
- 若正式来源建构所需角色/权限/Bundle 不存在，记录具体缺口并转到可独立推进的产品配置入口，不把合成夹具当正式权限。

未动当前新库、商城源、旧十二 Run、Provider、Runtime Host。P2g30b 仍**未完成**，不能推进 P2g30c 或声称返工自然续跑。
