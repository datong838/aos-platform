# W5c7p Claim Loop 身份与不可变负例 verification（2026-09-25）

## 第 1/9～4/9 步

- 复习 231/231-5、W5c7o、ClaimLoop/a0v_024/专用 PG fixtures；文件级方案 `0812c672` 先提交。新测试与只读审计 `3693293e`，未改生产 `aos_api/`、迁移、真实 DB/部署。
- 新 3 项：错连接/线程/事务/tenant/actor/member 和已失效 loop 均拒绝；原 claim 持久后 runtime UPDATE/DELETE 被权限拒绝，管理员 UPDATE/DELETE 被 immutable trigger 拒绝，异租户 RLS 读回 0。首跑测试用数字下标读取 dict row 导致 1 failed，这是测试缺陷，不计通过；改为命名列后专项 **3 passed**。

## 第 5/9～7/9 步

- 专用 18432 PG 新测试 + W5c7o + 原 InputOwner/SourceClaim Owner **37 passed**；既有 Host/closure、W5c5k–z/W5c6a–z/W5c7c/e/f/h/j/m/JDBC 短累计 **224 passed**。W5c7n 旧长例 1 passed 事实保持，本波未重跑。
- 临时 `aos_test_%` DB 0、`ar1c_%` schema 0；专用 18432 与 5433 测试 PG 均已停。
- 真实 gate 仍 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、12 原 Run running、stalled Receipt 0、`automaticAction=false`、`closureAuthorized=false`。浏览器只读 A0-V Canonical rev4「已配置 · 已停用」，运行状态「数据组已停用」（2026/9/25 17:23:29），当前身份无权启用；待同步写操作 1 未冲刷，临时 Vite 已停。
- 历史 claim 不可变不代表当前安装/控制/Run 不变；本波没有完整当前状态跨会话并发锁序证明，**同一 `_load` claim 复用仍未获授权**。旧真实 attempt 不重发、不手工 `run_definition`；商城源行不读、230 L0 挂起、dev-org 零 canary、m1 单写不 push。

## 第 8/9～9/9 步

本 verification 提交后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立长记忆并读回。下一波 **W5c7q**：先方案，专用隔离 PG 做当前安装/控制/Run 的有界并发可见性和锁序对抗；无等价证明则保留原读回，不触真实 closure。
