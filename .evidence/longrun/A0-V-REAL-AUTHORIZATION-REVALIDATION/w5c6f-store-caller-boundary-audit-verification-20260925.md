# W5c6f Store caller 边界无效应审计核验（2026-09-25）

方案 `bc7dc3d6` 先行、无效应合同 `c2d278cf`。本波未改生产 caller/Store、真实 DB/Host。

## 九步证据

1. 复习 O1 Store Receipt/Outbox、W5c6a–e、Single/Link/Retirement 的 preparation、独立 effect 和后续 readback。
2. 文件级仅新增 `test_a0v_w5c6f_store_caller_boundary.py` 与本 verification。
3. 合同证实四个 effect 调用点仍未传 Host lease：Single base `apply_batch`、逐条 derived `update_derived_metrics`、Link strict apply、Retirement strict apply；metadata 先提交，Store 自有事务后提交，再核原 command。W5c6e 仅开放默认关闭 API，未改变上述现状。
4. deadline/cancel 检查只界定是否继续，不能把两种事务变原子；derived 多条各有独立 Receipt，失权/未知提交必须只读对账，不能换 key 重发。
5. 专项 **3 passed**，W5c5k–z 加 W5c6a–f 累计 **58 passed**。旧 Single ingress PG 12 skipped、旧 Object 2 skipped、旧 Schedule 完整套件超时、Attempt PG 17 skipped、`AOS_DATABASE_URL` 顺序债仍在。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行、冲刷队列，页面/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格资格仅在 `2026-09-25 20:00:04.800482 UTC` 后。真实库缺 `a0v_094`、caller 未 opt-in；W5c6e `FOR SHARE` 阻塞续租/长事务到期风险未消除，不授权真实 effect。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6g：先方案设计 bounded Store transaction timeout/lease 续租兼容及提交边界；隔离 PG 证明后再考虑 caller opt-in，当前继续 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
