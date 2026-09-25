# W5c7r Installation 锁与时间窗重验 verification（2026-09-25）

## 第 1/9～4/9 步

- 复习 231/231-5、W5c7q、SourceSelection/RuntimeControl/GroupOwner；方案 `0077e3fc` 先提交。新隔离 PG 测试/审计 `cbde5f5b`，未改生产 `aos_api/`、迁移、真实 DB/部署。
- 原始 saved group 消费事务 callback 内，第二会话对 exact `bundle_installation` 行 `FOR UPDATE NOWAIT` 得 `55P03`，原事务提交后可取锁，零业务行更新。另一独立用例在 callback 后测试侧把 GroupOwner `_now` 注入为 `expires_at`，后置原 `_validate` 拒绝且 source call 仍 1；**这只是时间越界调用合同，不是实际 DB 时钟经过**。专项 **2 passed**。

## 第 5/9～7/9 步

- W5c7r/q/p/o + 原 InputOwner/SourceClaim Owner 专用 PG 联合 **40 passed**；Host/closure、W5c5k–z/W5c6a–z/W5c7c/e/f/h/j/m/JDBC 短累计 **224 passed**。W5c7n 旧长例 1 passed 保持，本波未重跑。
- 临时 `aos_test_%` DB 0、`ar1c_%` schema 0；两个隔离 PG 用后已停。
- 真实 gate 仍 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、12 原 Run running、stalled Receipt 0、`automaticAction=false`、`closureAuthorized=false`。浏览器只读 A0-V Canonical rev4「已配置 · 已停用」，运行状态「数据组已停用」（2026/9/25 18:04:07），当前身份无权启用；待同步写操作 1 未冲刷，临时 Vite 已停。
- 安装行锁覆盖 callback、后置时间窗守卫会再调用；但 completed/saved recovery、配置/预算/发布派生依赖与原错误语义未获完整等价证明，**生产 claim 复用不授权**。旧真实 attempt 不重发、不手工 `run_definition`；商城源行不读、230 L0 挂起、dev-org 零 canary、m1 单写不 push。

## 第 8/9～9/9 步

本 verification 提交后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立长记忆并读回。下一波 **W5c7s**：先方案，审 completed/saved recovery 和异常语义，形成同事务候选切片的综合可行性结论；不触真实 closure。
