# W5c7s Claim 优化裁决 verification（2026-09-25）

## 第 1/9～4/9 步

- 复习 231/231-5、W5c7l–r、InputOwner 原始 running/completed 与独立 saved recovery 路径；方案 `738ad50b` 先提交、综合只读审计 `02d0e40a`。本波未改生产/测试代码、DB、索引或部署。
- completed PG 8 passed（只读、不完整成员、缺/坏 Receipt、当前发布复核）；saved recovery Authority 2 passed（持久会员权限、回调中时间窗/异步拒绝）；恢复运行 5 passed（disabled、actor、stale ref、failed-unknown、负租户均不到 Store）。
- 原始 running 每次 `_load` 逐成员 `_bound_parent`；completed 还要求 succeeded/executor stopped/derived+dataset receipt/零 pending；saved recovery 独立 `_run_recovery`，callback 前后 `read_saved_current`/`read_completed_current`，不走原 `_bound_parent`。三路径异常与权限不可互换。

## 第 5/9～7/9 步

- Host/closure、W5c5k–z/W5c6a–z/W5c7c/e/f/h/j/m/JDBC 短累计 **224 passed**；W5c7n 长例 1 passed/794.823 秒正式 GREEN 保持，本波不重跑。临时 `aos_test_%` DB 0、`ar1c_%` schema 0；隔离 PG 已停。
- 真实 gate 仍 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、12 原 Run running、stalled Receipt 0、`automaticAction=false`、`closureAuthorized=false`。浏览器只读 A0-V Canonical rev4「已配置 · 已停用」，运行状态「数据组已停用」（2026/9/25 18:13:00），当前身份无权启用；待同步写操作 1 未冲刷，临时 Vite 已停。
- **裁决：生产性能优化延期。** 旧长例已在 900 秒预算内 GREEN，当前优化收益不抵完整等价性尚未证明的风险；保留双 `_load`、逐成员 claim/parent 重验、completed 与 recovery 独立守卫和原异常语义。W5c7o–r 负例/锁证据不是生产优化授权，也不是 A0-V 业务完成。
- 旧真实 attempt 不重发、不手工 `run_definition`；商城源行不读、230 L0 挂起、dev-org 零 canary、m1 单写不 push。

## 第 8/9～9/9 步

本 verification 提交后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立长记忆并读回。下一波 **W5c7t**：先方案，回到全机 Host universe/worker coverage 的真实可部署控制面来源与 fail-closed 接入前提；本地进程/DB session 不算完整 topology，不启动真实 closure。
