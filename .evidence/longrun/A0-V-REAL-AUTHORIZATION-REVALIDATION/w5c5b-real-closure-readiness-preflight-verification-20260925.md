# W5c5b 真实关闭只读预检分层核验（2026-09-25）

上位 231 A0-V/231-9 BG-00；方案先行 `56fa44e3`，实现/方案细化 `527d64df`。本脚本只输出建议，不调用正式关闭 Owner。

## 九步证据

1. 复习 W5c4t DB-clock 严格门、W5c4s 定义禁用独立审计、`a0v_091` SQL/Service。
2. 文件仅本方案、新增 `scripts/a0v_w5c5b_real_closure_preflight.py` 与 `services/aos-api/tests/extension_runtime/test_a0v_w5c5b_real_closure_preflight.py`、本 verification。生产 Owner/迁移不改。
3. 复用 W5c4t 只读观察与 W5c4s 精确 rev4/disable key/current member/12 schedule off/唯一失败 attempt/已停历史 Host PID/既有 18181 worker 观察，另只读查 actor 当前 admin。双采样不具事务原子性，因此只作路由建议；缺项冻结。
4. 首次专项因前波已停隔离 PG，仅得到 4 个连接拒绝 setup ERROR，未进入断言；启动专用测试库后 **4 passed**，覆盖 <24h、等于 24h、到线仅建议、actor/拓扑/定义/第二 attempt/缺项冻结。真实脚本两次读回 `STALLED_WAIT_24H`、`automaticAction=false`、`topologyComplete=false`。
5. 最终有界累计 W5c3–W5c5b、定义、attempt、lease、preparation **196 passed，7 warnings，29.50s**；隔离测试库已停止。更宽慢集此前中止不算 GREEN。
6. 浏览器 5174 只读见 12 单路计划与整组入口；不证明后端门，`BROWSER_PARTIAL`。未保存、运行或冲刷队列；临时页/前端已关闭。
7. 即使 DB 严格 24h 过线，脚本仅 `REQUIRES_SEPARATE_REAL_CLOSURE_PLAN`；正式 key/intent、全机第二 Host 排除、执行事务内全门禁与独立审计仍未完成。`topologyComplete=false` 是显式风险，不得将预检当真实关闭授权。当前仍 `STALLED_WAIT_24H`，严格最早 `2026-09-25T20:00:04.800482+00:00` 后。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆，读回。
9. 下一波 W5c5c：完成剩余只读拓扑/角色证据或安全研发债；到线后独立真实关闭方案、唯一 Owner 动作、独立 DB 审计、定义退休。

m1 单写不 push；商城源行不读；旧 attempt 不补跑；dev-org 零 canary；230 L0 挂起，A0-V/BG-00 未过。
