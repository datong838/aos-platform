# W5c6i DB Owner / Store effect 原子边界无效应审计方案（2026-09-25）

上位 W5c6a–h：Store effect 的独立 SQLAlchemy 事务可默认关闭 opt-in Host fence，但 lease 续租被原事务 share lock 阻塞、整笔事务时长无硬上界；四个 caller 仍未接线。正式 stalled closure `a0v_091` 是受限 maintainer + SERIALIZABLE 的独立事务，只关闭旧 group，不是 Store effect 授权。不能把二者合并为“已原子化”。

## 文件级九步

1. 复习 `a0v_091` closure SQL/服务的 maintainer 角色与单事务收据、`a0v_093/094` Host 排他、Store base/derived Receipt 和 Single/Link/Retirement caller 提交边界。
2. 本方案先提交。本波只新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c6i_owner_store_atomicity_boundary.py` 无效应合同与 verification；不改生产 SQL/Store/closure/Host 或真实 DB。
3. 合同固定：closure service 使用 `consumer_connection` + SERIALIZABLE + `aos_extension_maintainer`，回读 closure Receipt；Store effect 使用另一 `engine.begin()` + `aos_runtime`；现有接口不接受同一事务连接。`a0v_091` 的严格 24h/12 Run 资格不可借 Store effect 跳过。
4. 评估候选 A：先正式 closure，再 direct successor 的精确新 generation/Receipt；候选 B：新增 DB 单事务 owner/effect 组合须重设计角色、RLS、idempotency 和 external source effect，不能在本波拼接。未知提交边界一律只读对账，不重发。
5. 静态专项与 W5c5k–z/W5c6a–i 累计回归；无 Store/商城源写入，历史 skips/timeout 如实列。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 实时关闭门禁只读；没有完整 Host 拓扑与单事务 Owner 新授权时不调用 closure，不迁移真实 `a0v_093/094`。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6j：按正式 closure 前置条件做全机 Host 拓扑只读证据设计与可执行发现器；若证据不足继续 no-effect，不从 UI/单进程推断全机唯一性。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
