# W5c5y Single Executor→Object opt-in lease 传递核验（2026-09-25）

方案 `bbc6770a` 先行，实现 `9a126174`。真实 DB 仍 `a0v_092`，Host flag 未启用。

## 九步证据

1. 复习 Single Executor 构造与 `_finish`、Object 内部 `resume_saved`、Link/Retirement/Completion 上层构造及 W5c5x ingress guard。
2. 只改 `pipeline_controlled_executor.py` 和 `pipeline_snapshot_group_object_executor.py` 的可选精确 lease 传递；新增 W5c5y 隔离 PG 测试、更新 W5c5r 静态合同。未改 Link/Retirement/Completion/Store。
3. 默认 None 不变；显式 opt-in 时 Object 自身局部 metadata 事务和内部 Single ingress 多笔独立事务共享同一 `OptInHostLease`。Object 自身局部事务存在同租约双重 guard，安全冗余，不替代跨 Store commit 的排他保证。
4. 新专项加结构合同 **5 passed**：精确类型、默认路径、同实例传递、未 acquire/失权拒绝和内外事务有效持有人。
5. W5c5k–y 围栏/结构组 **37 passed**；旧 Single ingress PG 12 skipped（W5c5x 已证）、旧 Object 2 skipped（W5c5w 已证），不能记作绿灯。此前主组 162 与定义合同 24 为历史基线，本波未重跑。旧 Schedule 完整套件超时、Attempt PG 17 skipped、`AOS_DATABASE_URL` 顺序债保留。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行或冲刷队列，临时页面/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0，严格资格仅在 `2026-09-25 20:00:04.800482 UTC` 后。顶层未传 lease、Store effect 跨独立提交边界，绝非全链路排他；不得关闭旧组或重发旧 attempt。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文和 Prime 独立受管记忆并读回。
9. 下一波 W5c5z：Link→Object、Retirement→Link、Completion→Retirement 可选 lease 逐层传递；Store effect 保持独立风险门。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。
