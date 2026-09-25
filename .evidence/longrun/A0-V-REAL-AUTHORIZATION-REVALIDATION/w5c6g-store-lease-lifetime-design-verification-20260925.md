# W5c6g Store lease 生命周期设计核验（2026-09-25）

方案 `90822932` 先行、无效应合同 `4b817564`。未改生产 Store/Host/caller、真实 DB。

## 九步证据

1. 复习 W5c6e/f、Host lease TTL/renew、`a0v_094` 的 `FOR SHARE` 与数据库时钟、Store `engine.begin()` 和四个独立 caller effect。
2. 文件级仅新增 `test_a0v_w5c6g_store_lease_lifetime_design.py` 与本 verification。
3. 当前 lease TTL 5–30 秒、renew 间隔小于半 TTL；worker guard 在调用方同事务取 share lock、用 DB clock 检查 expiry，不独立连接。锁冲突会拖延 renew；W5c6e 隔离证明长事务到期时末次 guard fail closed。
4. Store 有写前与 base/derived replay/new-write 返回前 guard，但没有整笔事务最大耗时门；`statement_timeout`/`lock_timeout` 即使后续加入也只约束 SQL/等待，不等同全事务上界。metadata 与 Store 独立提交，不宣称原子排他或持续可用。
5. 专项 **3 passed**，W5c5k–z 加 W5c6a–g 累计 **61 passed**。旧 Single ingress PG 12 skipped、旧 Object 2 skipped、旧 Schedule 完整套件超时、Attempt PG 17 skipped、`AOS_DATABASE_URL` 顺序债仍在。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行、冲刷队列，页面/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格资格仅在 `2026-09-25 20:00:04.800482 UTC` 后。真实库缺 `a0v_094`、caller 未 opt-in；在总时长/提交边界未闭合前不传播参数。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6h：隔离 PG 证明有限 Store 事务上界与 lease 续租争用的可执行门禁；若不能满足，继续 no-effect 并研究 DB owner 与 Store effect 同事务替代。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
