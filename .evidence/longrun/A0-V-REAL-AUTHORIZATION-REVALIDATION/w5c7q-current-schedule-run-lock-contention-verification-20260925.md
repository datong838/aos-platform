# W5c7q Schedule/Run 锁对抗 verification（2026-09-25）

## 第 1/9～4/9 步

- 复习 231/231-5、W5c7l/o/p、组守卫/Journal 锁序；方案 `e796aa6c` 先提交，隔离 PG 新测试与审计 `6c99d57f`。无生产代码、迁移、真实 DB/部署改动。
- 原始 2-member saved input 的 `run_current` 消费事务 callback 内，第二专用 PG 会话对 exact Schedule 与 Run 发 `SELECT ... FOR UPDATE NOWAIT`，均得 `55P03 LockNotAvailable`；原事务提交后，同样只读锁请求均成功。原 source call 仍 1、消费结果 2 parents；零业务行更新。新专项 **1 passed**。

## 第 5/9～7/9 步

- W5c7q/p/o + 原 InputOwner/SourceClaim Owner 专用 PG 联合 **38 passed**；Host/closure、W5c5k–z/W5c6a–z/W5c7c/e/f/h/j/m/JDBC 短累计 **224 passed**。W5c7n 旧长例 1 passed 保持，本波未重跑。
- 临时 `aos_test_%` DB 0、`ar1c_%` schema 0；两个隔离 PG 用后已停。
- 真实 gate 仍 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、12 原 Run running、stalled Receipt 0、`automaticAction=false`、`closureAuthorized=false`。浏览器只读 A0-V Canonical rev4「已配置 · 已停用」，运行状态「数据组已停用」（2026/9/25 17:40:54），当前身份无权启用；待同步写操作 1 未冲刷，临时 Vite 已停。
- 对照源码：Schedule `FOR UPDATE`、Run `FOR SHARE` 持续覆盖 callback；但安装/控制最新 revision、DB 时钟、completed/saved recovery 与错误码等价未完成证明，**生产 claim 复用不授权**。旧真实 attempt 不重发、不手工 `run_definition`；商城源行不读、230 L0 挂起、dev-org 零 canary、m1 单写不 push。

## 第 8/9～9/9 步

本 verification 提交后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立长记忆并读回。下一波 **W5c7r**：先方案，在隔离 PG 对安装/控制最新 revision 的并发可见性和 DB 时钟窗口做负例；仍不动真实 closure。
