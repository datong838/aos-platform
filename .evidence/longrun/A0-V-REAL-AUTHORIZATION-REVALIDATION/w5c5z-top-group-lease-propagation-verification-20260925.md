# W5c5z 顶层 group opt-in lease 传递核验（2026-09-25）

方案 `2158bf3a` 先行，实现 `942d3625`。真实 DB 仍 `a0v_092`，Host flag 未启用。

## 九步证据

1. 复习 Link、Retirement、Completion 的构造及原 `_transaction` 委派；审查 Link/Retirement 独立 Store effect 与 W5c5y 下层链路。
2. 仅 Link/Retirement 构造增加可选精确 `OptInHostLease` 并下传，Completion 将既有同 lease 传 Retirement；新增 W5c5z 隔离 PG 测试、更新 W5c5r 静态合同。Store/Host/真实 DB 未改。
3. 默认 None 不变；显式 opt-in 时 Completion→Retirement→Link→Object→Single→ingress 同一 holder，每笔 metadata 事务独立 guard；Completion Attempt 心跳/settle 已使用同 lease。多笔事务并非跨 Store effect 原子排他。
4. 新专项加结构合同 **5 passed**：精确类型、默认、同实例链路、有效 holder 与失权后五层 metadata body 前拒绝。未执行真实 group 或 Store effect。
5. W5c5k–z 围栏/结构组 **39 passed**。旧 Single ingress PG 12 skipped、旧 Object 2 skipped 为此前已知，不计绿灯；旧 Schedule 完整套件超时、Attempt PG 17 skipped、`AOS_DATABASE_URL` 顺序债保留。此前主组 162、定义合同 24 为历史基线，本波未重跑。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行或冲刷队列，临时页面/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格资格仅在 `2026-09-25 20:00:04.800482 UTC` 后。Store effect 与跨机器 Host/worker 排他未证，真实 DB 未迁移；不得关闭旧组或重发旧 attempt。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文和 Prime 独立受管记忆并读回。
9. 下一波 W5c6a：梳理跨 Store effect 的 fail-closed epoch 校验/回执边界，先做无效应方案与专项合同，不能以本波 metadata 传递替代实际排他。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。
