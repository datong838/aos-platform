# d2b3c4b 已接受方案内容生成执行前权威复核验证

方案：同目录 `w5cb4-gwb2c2c1b3c2d2b3c4b-content-admission-plan.md`；上位231-5 §5、§9。

| 步骤 | 本次证据 |
| --- | --- |
| RED | `pytest ...test_ecommerce_content_generate_handoff_lineage.py -k revalidates_execution_authorities_before_closed_gate`：预期当前路由预算拒绝，实际为 `accepted stage content Host is not wired`；1 failed、23 deselected，退出1。 |
| 最小实现 | 仅在新 `accepted-stage-v1` 生成 Host `revalidate` 分支复用既有 Agent/Capability、ModelRoute/Budget/Approval、事实来源、Resolution/Capacity、Binding 与依赖读者；数据库当前检查时间再核原 Stage cutoff/expiry。旧四 Artifact 分支、`execute`、`verify_receipt`、Provider 未改。 |
| 专项/相邻 | 原 Stage 生成合同、隔离 PG Owner 前缀、Binding、路由预算、Resolution/Capacity 五文件 `110 passed, 7 warnings`，退出0。专项还证明路由拒绝与事实来源拒绝会中止，授权在两次检查间过期会中止；六读者通过仍落在 `Host is not wired`。读者替身只证明顺序，不证明任何当前实例具备正式配置。 |

复审：本次没有预算 reserve、Provider 调用、当前真实库写入、正式 Host 开启或业务首链通过。原 Analysis producer 仍被正式 G2 Skill Eval 来源门阻断；持久化原 Review Receipt、生成执行和人工评审同源消费者尚无联合正向。当前真实库只读，租户只认 `org-org/dev-project`，`dev-org` 不作正向。

提交后复验：`m1@e9b6ab12`；`launchctl kickstart -k gui/$(id -u)/com.aos.a0v-api-daily0900` 退出0，API `/v1/health`、`/v1/ready` 与 Web `/aip/skill-publish` 均 HTTP200。Codex 浏览器回读显示 `org-org/dev-project`、37项仅评测/0发布、缺正式放行/Logic/路由三来源、按钮 disabled、无电商工作台入口；截图 `w5cb4-gwb2c2c1b3c2d2b3c4b-browser-20261002.png`，完整 AX 状态见本轮工具记录。页面可访问与禁入不等于首链完成。
