# W5c6g Store 原事务与 Host lease 生命周期设计方案（2026-09-25）

W5c6e 隔离 PG 已证实 `a0v_094 FOR SHARE` 在 Store effect 事务内持有行锁，directory 续租 UPDATE 因此会等待；长事务跨 TTL 后，返回前 guard 以数据库时钟拒绝并回滚。W5c6f 又证实四个 caller 均未传 lease。现在缺的是受控时长/失败恢复证明，而非更多无界传播。真实库缺 `a0v_094`。

## 文件级九步

1. 复习 W5c6e/f、`OptInHostLease` TTL/renew、SQL `a0v_093/094` 锁与 clock、Store `engine.begin()`、Single/Link/Retirement deadline/Receipt 语义。
2. 本方案先提交。本波仅新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c6g_store_lease_lifetime_design.py` 无效应合同和 verification；不改生产 Store/Host/caller/真实 DB。
3. 定义安全条件：每次 opt-in effect 的独立 Store 原事务在首个 guard 到最终 guard 之间必须以 DB expiry 判定；任何等待续租、超时、异常都回滚或保持“提交未知→只读对账”，不得自动重发。跨事务 metadata 不能承诺原子性。
4. 设计候选：Store 独立事务内设置有界 `lock_timeout`/`statement_timeout` 只约束单条 SQL，不是全事务时钟；应用 monotonic deadline 只可在控制流检查，不能中断正在执行的任意 SQL；最终 DB guard 是必要但不足以保证无限长事务可用性。不得因近似时间推断 live effect 权限。
5. 无效应合同锁住当前 TTL 5–30 秒、续租间隔小于半 TTL、Store 未声明全事务上界、caller 仍未 opt-in；专项加 W5c5k–z/W5c6a–g 累计回归。隔离 PG 在 W5c6e 的锁/expiry 证据不重复对真实库写入。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 复审：若无法在现有 PG/调用结构下证明有界总时长和提交边界，则下波不能传播 Store lease，只能先设计替代（短事务拆分、DB 内单事务 owner/receipt-first）。实时关闭门禁只读。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6h：在隔离 PG 设计并验证“有限事务上界 + lease 续租争用”的可执行门禁；若不能满足，保持 no-effect，优先研究 DB owner 与 Store effect 同事务的替代。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
