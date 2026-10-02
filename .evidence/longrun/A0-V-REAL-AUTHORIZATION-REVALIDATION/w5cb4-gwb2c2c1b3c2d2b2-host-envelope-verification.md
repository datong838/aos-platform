# GW-b-2c2c1b3c2d2b2 宿主生成命令禁入验证

基线 `AOS-001125` / `m1 3789b753`，Task `W5CB4-GWB2C2C1B3C2D2B2-20261002`；方案 `w5cb4-gwb2c2c1b3c2d2b2-host-envelope-plan.md`。已复习 231-5 §1/§9 与栖月汇六同事统一合同。

- RED：新 `accepted-stage-v1` 单原 `Artifact` 命令在宿主 `_strict_content_generate_command` 被 `content generate command envelope drifted` 拒，1 failed/20 deselected，退出1。
- 最小实现：宿主只接受精确 `sourceKind=accepted-stage-v1` 加单原 `Artifact`；旧四 `ArtifactRevision` 命令无新字段，旧 ReturnDecision 分支不变。新分支 `sourceKind` 进入 requestHash，混用四源、伪造旧种类、重复源、ReturnDecision 混用都拒。
- 零副作用：新命令即使绕过包内前置门，Host `revalidate/execute/verify_receipt` 都在数据库访问和预算保留前 `accepted stage content Host is not wired`；测试用拒绝任何 SQL 的事务替身，三个入口均失败关闭。包内执行仍 port 命令0/Provider调用0。
- 回归：首次五文件相邻 67 passed/1 failed，失败是上一波预期“宿主仍拒 envelope”的测试断言过期，已更新为当前严格解析加 Host 禁入；同五文件 68 passed、7 warnings，退出0。最后只收紧旧 `verify_receipt` 语义为仅新分支预检，专项2 passed；`py_compile`与`git diff --check`退出0。
- 复审：此波只接命令语法和禁入，未实现 v3 Task/Brief、原 Stage Owner、ReviewDecisionReceipt 或可读 Artifact 的新来源验证。真实库只读且自动测试使用可销毁隔离 PG；无真实生成、预算保留、Provider调用或首链证明。
- 代码提交 `m1@e8f5a150` 后，`launchctl kickstart -k` 重载 API/Web，当前 PID35451/35454 均重新监听 8080/8434；PG 仍是当日已完整重启的同一权威卷。Codex 浏览器重新加载 `/aip/skill-publish`，实见 37 仅评测、发布0、正式发布/Logic/模型路由三 blocker、按钮 disabled 和“暂无可见工作台入口”；截图在本波浏览器工具输出。此 UI 只验证禁入保持，不验证 Host 新命令的自然执行。

下一切片 d2b3：原 StageDecision/TaskRun/Plan/Attempt/Eval/Artifact/permission、获批 GrowthPlan 与 v3 Task/Brief 同事务 exact 回读，接 Review Receipt 和人工评审双消费者；齐备前 Host 不开。当前正式 API/Host 身份、八配置/assignment/binding、Growth1.13 发布仍属独立 P0。
