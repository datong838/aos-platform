# W5c7p Claim Loop 身份与历史行不可变审计

在专用 18432 隔离 PG，W5c7p 新合同确认 `_ClaimLoop` 只能在原连接、线程、事务、scope、actor 和固定 run/control pair 中继续；错项与失效 context 均拒绝。原始 claim 已持久后，`aos_runtime` 不能 UPDATE/DELETE；管理员也被 `immutable_history` trigger 拒绝；同一 runtime 用 `dev-org` tenant context 读取原 `org-org` claim 为 0。新 3 项、结合 W5c7o/原 InputOwner/SourceClaim Owner 37 项均通过，失败尝试回滚且 fixture claim 数不变。

上述只证明 loop 身份与历史行不可变。`PipelineSourceClaimOwner._operate` 每次仍经过当前安装/控制/调度守卫、run lock、原 claim 比对；历史行不可变不能替代这些当前读。W5c7o 同一 `_load` 复用优化仍未证明锁序/跨会话并发可见性，completed 与 saved recovery 分支也不能从 running 合同外推。生产 `_bound_parent`、claim Owner 与真实 A0-V 均保持原状。下一波须专门做有界并发锁序测试；若无法建立完整等价，继续保留原读回。
