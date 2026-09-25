# W5c6h 隔离 PG Store 围栏时间预算验证方案（2026-09-25）

上位 W5c6e–g：Store 原事务 `a0v_094 FOR SHARE` 阻塞 lease renew；末次 guard 可在 TTL 到期时回滚，但未证明整笔 Store 事务有界。真实库缺 `a0v_094`、caller 未 opt-in。仅在隔离 PG 验证可执行失败门，不把单语句超时误记成事务总时长约束。

## 文件级九步

1. 复习 Host lease SQL clock/锁、W5c6e 的 5 秒到期测试、Store 原 `engine.begin()` 与 receipt/new-write 返回、W5c6g 设计合同。
2. 本方案先提交。只新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c6h_isolated_store_time_budget_pg.py` 和 verification；不改生产 Store/Host/caller、真实 DB。
3. 隔离 PG 的 runtime Store 事务设置 `SET LOCAL lock_timeout`/`statement_timeout`，验证它们只作用 SQL 等待/单语句；与 concurrent directory renew 冲突时不承认 effect 成功，事务回滚或明确失败。
4. 在有效 lease 下用独立 runtime Store 原事务确认短路径可提交，模拟过期/失权在末次 guard 前被拒绝；比较 DB clock 与客户端 monotonic，不用本地时间替代 DB 授权。
5. 专项隔离 PG + W5c5k–z/W5c6a–h 累计回归；无真实 Store 行、无商城源数据。若环境缺少相关 GUC 或行为不符，冻结为设计债，不接 caller。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 复审：单语句/锁 timeout、应用 deadline、末次 DB guard 组合仍非严格总事务 deadline，也不能消除末次 guard 到 commit 的边界；结论只限 fail-closed 可行性。真实关闭门禁只读。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6i：研究独立 DB owner 与 Store effect 同事务/Receipt-first 的替代边界及正式拓扑证据，不启真实调用；先方案与无效应合同。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
