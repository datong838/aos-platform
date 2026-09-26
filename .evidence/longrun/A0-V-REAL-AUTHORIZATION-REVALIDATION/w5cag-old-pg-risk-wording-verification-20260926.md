# W5cag｜旧 PG 当前风险措辞校准核验（2026-09-26）

方案 `f9d57e61`、补订 `dbda3f37` 先行；逐项审计 `789c2a13`。本波无生产/测试代码、数据库或 worker 变更。

## 九步证据

1. 上位 231 A0-V/BG-00 和 W5c5x/y/z 复习完成。W5c5y/z 的显式 opt-in lease 下传是已测试实现，不能继续写成“完全未传”；生产尚未接线。
2. 文件仅本目录 plan、audit、verification；authority CAS 和受管投影随后执行，不改旧 verification。
3. AOS-000730 当前 34 项中仅定位第 21/22 项；W5caf 24 项 collect 精确 12（Single ingress）+4（Executor integration）+8（Object），正式 24 passed。历史 W5c5x/y/z skipped 保留原文。
4. 计划将当前两条改为“旧隔离 PG 已通过、显式 opt-in 下传已证；生产 Host flag/真实迁移/全机排他和 Store 跨独立提交 effect 未证”。其余 32 条不改，next gate 不变。
5. 无代码专项；使用已提交的 W5caf 测试终态与本波 `git diff --check` 作累计依据，不重复启动 18432。`memory-status/validate` 和 34 项数量在 CAS 后读回。
6. 18181 仅 HTTP-only 文档只读可用；8080 业务浏览器仍离线，真实业务验收不具条件；未调用 API 执行。
7. 方案/审计结论一致：本波只修正“当前风险中的历史 skipped/未传递”两处时间语义，不删除生产 Store/Fleet/Owner/原 12 Run 禁令，也不将隔离测试冒充真实授权。
8. 本 verification 先提交，再 CAS AOS 项目上下文/Prime 受管记忆、读回并提交精确上下文。
9. 下一波：评估剩余 32 项中真正可安全减少的独立技术债；没有可信全机 Fleet/旧入口撤权和独立历史行证明或正式 no-business-acceptance 退休选择时，原组 ACK/closure/replay 保持冻结。230 L0 挂起，dev-org 零 canary，m1 单写不 push。

## CAS 与记忆读回

CAS `AOS-000730→AOS-000731`；对比提交前 authority，`incomplete` 总数 34，**仅索引 21/22 变化**，其余 32 项完全一致。docs 上下文/受管记忆 `docs/m1@a9d2a622`，`delivery_status=W5CAG_OLD_PG_RISK_WORDING_RECONCILED_REAL_A0V_FROZEN`，下一门不变。`memory-status` GREEN_WITH_WARNINGS：共享/上下文/Prime 强一致投影 CURRENT，Codex 注记 PENDING_ASYNC；`memory-validate` GREEN。真实 A0-V 仍冻结。
