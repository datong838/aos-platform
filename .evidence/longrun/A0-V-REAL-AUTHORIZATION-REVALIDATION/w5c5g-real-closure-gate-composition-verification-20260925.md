# W5c5g 真实关闭门只读组合判定核验（2026-09-25）

上位 231 A0-V/231-9 BG-00；方案 `22ecb5eb` 先行，实现 `2e6f1e8b`。本波无真实关闭 intent/key/Owner 调用，无商城源行读取。

## 九步证据

1. 复习 W5c5b–f 各自 verification、严格 24h 和 `a0v_091` 正式关闭门。
2. 文件仅本方案、新增 `scripts/a0v_w5c5g_real_closure_gate_composition.py` 与 `services/aos-api/tests/extension_runtime/test_a0v_w5c5g_real_closure_gate_composition.py`、本 verification；Owner/Host/迁移零改。
3. 组合已有只读时间/原组门、本机已知 Host 进程及角色门、正式受管 connector、独立 Receipt 审计、受管 Host 目录门；显式承认各门并非跨面原子快照。真实输出 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`，严格在 `2026-09-25T20:00:04.800482+00:00` 之后才可能满足时间门，原 12 Run running、stalled Receipt 0；全机拓扑、单事务 Owner 门、独立真实方案/唯一 key 仍待办。
4. 专项 **16 passed**，覆盖时间等待、到线但仍不授权、任一门冻结/Receipt 变化/Run 漂移；`closureAuthorized=false`、`topologyComplete=false`、`automaticAction=false`。
5. 有界累计 W5c3–W5c5g 与定义、attempt、lease、preparation **252 passed，7 warnings，31.55s**；隔离 `aos-dev-pg` 已停止；`git diff --check` 通过。
6. 5174 浏览器只读见 12 单路计划和 A0-V 整组 rev4 已停用；`BROWSER_PARTIAL`，页面不能证明 DB 或全机门。未保存、运行或冲刷队列，临时页/前端已关闭。
7. 方案/代码一致：组合器只是缺口诊断，不生成 key、不调用 Owner、不提供事务锁或跨机器进程证明。任何未知冻结；到线也不等于关闭授权。真实关闭需另立 plan→唯一 key→正式 Owner 一次→独立审计→退休/direct successor，A0-V/BG-00 未过。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5h：优先完成可验证的全机拓扑权威来源或其他不依赖关闭的安全债；不可凭本组合器执行真实关闭。

m1 单写不 push；旧 attempt 不补跑；230 L0 挂起；dev-org 零 canary。
