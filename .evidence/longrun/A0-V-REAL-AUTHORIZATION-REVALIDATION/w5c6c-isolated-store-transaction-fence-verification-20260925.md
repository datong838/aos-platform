# W5c6c 隔离 PG Store 自有事务围栏可行性核验（2026-09-25）

方案 `847067b1` 先行、读写事务形态补证 `7017fa03`，隔离合同 `ee844cbe`。生产 Store、真实 DB/Host flag 未改。

## 九步证据

1. 复习 Store `_apply_batch` 独立 SQLAlchemy `engine.begin()`、`_apply_transaction_scope`、W5c6b 真实只读审计和 `a0v_094` 的 `FOR SHARE` 锁。
2. 只新增 `test_a0v_w5c6c_isolated_store_transaction_fence_pg.py`；测试薄适配器将现有 `OptInHostLease.fence_in_transaction` 接到同一 SQLAlchemy transaction，不在独立连接检验 worker holder。
3. 隔离 PG 使用与 Store 一样的读写事务，但 Store body 仅 `SELECT`、不写 Store 行；lease fixture 可 acquire/模拟过期。默认/未 acquire、有效 holder 三笔、错 scope/epoch/过期均在业务 body 前分流。
4. 首轮把 Store 测试事务强制只读，`a0v_094` 的 `FOR SHARE` 导致 1 failed、1 passed；方案修正为 Store 原有读写事务形态后重跑 **2 passed**。此结论仅证明隔离适配可行，不能推出真实 Store API 已围栏。
5. W5c5k–z 加 W5c6a–c 累计 **48 passed**。旧 Single ingress PG 12 skipped、旧 Object 2 skipped、旧 Schedule 完整套件超时、Attempt PG 17 skipped、`AOS_DATABASE_URL` 顺序债仍在。此前主组 162 与定义合同 24 是历史基线，本波未重跑。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行或冲刷队列，临时页面/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格资格仅在 `2026-09-25 20:00:04.800482 UTC` 后。真实 Store 审计仍 `STORE_LOCAL_FENCE_NOT_READY`，真实库 `a0v_094` 缺失，不能接线、迁移、关闭旧组或重发旧 attempt。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文和 Prime 独立受管记忆并读回。
9. 下一波 W5c6d：方案先行设计 Store 原事务内可选 fence API、精确类型/同 scope/提交前校验/回执 replay 语义；隔离 PG 验证后再决定最小生产实现，真实默认关闭。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。
