# E17-s3o-c｜ToolBinding 当前撤销门 verification

基线 `m1@5fcc02e8` / `AOS-001187`；仅 `org-org/dev-project` 的 disposable PG，当前真实库只读。先读 231/231-9/W6-01/W-L20，文件级计划在同前缀 plan。

| 项 | 新鲜证据 |
|---|---|
| RED | 原 Resolver 的 ToolBinding、所属实例、CapabilityBinding 与 READY Plan 已形成；随后 `status='disabled'`，旧 `get_responsibility_plan` 仍 `ready`，`pytest -k revoked_tool_binding` exit1。 |
| GREEN | 6组撤销/漂移：Tool status/version、所属实例 status/归属、能力 Binding status/网络策略，均使 GET BLOCKED 和 freeze 被拒，freeze Receipt 0。3组两连接锁测：Tool、实例、能力绑定的并发 UPDATE 在写准入事务未提交时均 250ms 锁超时；提交后可撤销，只读 GET 变 BLOCKED。`pytest -k tool` exit0，10 passed；`pytest -k 'tool or provider'` exit0，17 passed。 |
| 相邻回归 | 原 Stage Review、W6-01、W-L20、W2B 和返工禁入专项组合 exit0，63 passed/7 warnings。`py_compile`、目标 diff check exit0。 |

复审：原职责消费点继续复用现有 Resolver 当前候选判定，比较 Receipt frozen exact Binding refs；工具写准入依次锁精确 ToolBinding、所属 AgentInstance、该工具声明的 CapabilityBinding，不读取租户全局替代。GET 不加行锁，Receipt 不改，未迁移真库。此波不证明 AgentInstance 作为独立 assignee 的 Skill/Capability 当前性；独立发行身份/ACL、正式配置、Host 与自然首链仍 pending。旧 RETURN 正向测试合同冲突仍需独立对账。
