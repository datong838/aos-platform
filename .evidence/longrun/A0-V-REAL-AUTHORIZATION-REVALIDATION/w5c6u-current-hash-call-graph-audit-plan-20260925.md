# W5c6u Current/哈希调用图安全审计方案（2026-09-25）

上位 W5c6t：Single 12 次约 33 秒，Object 总 110 秒、Link 总 199 秒、Retirement 到硬超时 264 秒；累计时间不能解释为单一慢成员。原 Object/Link/Retirement 多次 `read_current`/`run_current` 在不同事务边界重新验证，未审清前不能缓存或删除。

## 文件级九步

1. 复习 W5c6r–t、Object/Link/Retirement/Assessment/Policy 的 current 调用链与原 no-effect/事务边界。
2. 本方案先提交。本波只新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c6u_current_hash_call_graph_audit.py` 静态无效应合同与 verification；生产/DB/部署不改。
3. 列出 Object 12 成员逐次 current、Link 准备前后/Store 提交后 current、Retirement 准备/投影/完成 current；区分“同事务重复”与“跨独立提交必须重读”。
4. 只有同一事务内证据等价且可证明不破坏数据库时钟、RLS、权限、idempotency、投影读回的候选才可提出优化；本波不直接优化。
5. 静态合同专项与 W5c5k–W5c6t 累计回归；不做真实效应。
6. 浏览器只读 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 复审：静态调用图仅为风险/性能假设，不是 runtime profile；仍需测试专属每方法调用次数/耗时才可确定热函数。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立记忆并读回。
9. 下一波 W5c6v：按本波调用图，用测试专属计数/总耗时定位同事务重复调用；先方案后测试，真实 closure 仍 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
