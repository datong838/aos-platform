# W5c6h 隔离 PG Store 时间预算核验（2026-09-25）

方案 `1f69e165` 先行、隔离合同 `97f38265`。未改生产 Store/Host/caller、真实 DB。

## 九步证据

1. 复习 Host lease `a0v_093/094` 时钟与锁、W5c6e 5 秒到期、W5c6g 设计合同、Store 原事务/Receipt。
2. 文件级只新增 `test_a0v_w5c6h_isolated_store_time_budget_pg.py` 与本 verification。
3. 在隔离 PG 的 runtime Store 原事务设置本地 `lock_timeout`/`statement_timeout`；短事务有效 holder 两次 guard 通过。directory renew 持锁时，worker guard 在有界锁等待后拒绝；未执行 Store 行写入。
4. 单条 `pg_sleep` 超过 `statement_timeout` 使 SQL/事务失败；这仅证明每语句可截断，不能推出整笔事务受总时长约束，也不能用客户端 monotonic 替代 DB clock。
5. 专项 **3 passed**，W5c5k–z 加 W5c6a–h 累计 **64 passed**。旧 Single ingress PG 12 skipped、旧 Object 2 skipped、旧 Schedule 完整套件超时、Attempt PG 17 skipped、`AOS_DATABASE_URL` 顺序债仍在。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行、冲刷队列，页面/Vite 已关闭。
7. `lock_timeout`/`statement_timeout` 加最终 DB guard 可 fail closed，但不是完整事务总预算，仍有最终 guard 至 commit 的极短边界；因此不传播真实 caller。实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格资格仅在 `2026-09-25 20:00:04.800482 UTC` 后。真实库仍缺 `a0v_094`。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6i：研究 DB Owner 与 Store effect 同事务/Receipt-first 替代边界及正式 Host 拓扑，先方案与无效应合同；真实仍 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
