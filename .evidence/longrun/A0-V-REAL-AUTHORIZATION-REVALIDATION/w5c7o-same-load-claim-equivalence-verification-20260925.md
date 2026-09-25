# W5c7o 同一 `_load` Claim 复用负例 verification（2026-09-25）

## 第 1/9～4/9 步

- 复习 231/231-5、W5c7l/m/n、SourceClaim/GroupClaim/InputOwner/ClaimLoop 与 a0v_024 RLS/immutable。文件级方案先提交 `cc573f75`；新增隔离 PG 负例与审计 `f12f3de7`。无生产代码、DB、索引或部署变更。
- 初跑未启用 `AOS_EXTENSION_PG_TEST=1`，**3 skipped，不计通过**；按原套件合同启动专用 18432 PG、`--noconftest` 后新负例 **3 passed**。证实两次 `_load` 围住 callback，每次 parent 逐成员重验；GroupClaim 已过而 parent 重验拒绝时 consumer 未执行；callback 后 current deny 被第二次 `_load` 拒绝。
- 现有 completed 只读/当前 release 复核 **2 passed**；recovery Authority 持久权限复核 **1 passed**。这些是原行为合同，不是 claim 复用等价证明。

## 第 5/9～7/9 步

- 新 3 + 原 InputOwner 12：专用 18432 PG **15 passed**；Host/closure、W5c5k–z/W5c6a–z/W5c7c/e/f/h/j/m/JDBC 短累计仍 **224 passed**。W5c7n 旧长例 1 passed 的历史保持，本波未重跑。
- 临时 `aos_test_%` 数据库 0，`ar1c_%` schema 0；两个隔离 PG 用后已停。
- 真实 gate `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、12 原 Run running、stalled Receipt 0、`automaticAction=false`、`closureAuthorized=false`。浏览器只读确认 A0-V Canonical rev4「已配置 · 已停用」；本波运行状态子区块尚在加载时关闭，因此不把子区块终态列作本次新证据。未保存/运行/冲刷待同步写操作 1；临时 Vite 已停。
- 审计结论：`a0v_024` 历史行 immutable/RLS 不等于 current 控制不变；原 claim Owner 每次校验 source-claim loop 同连接/线程/事务/成员及当前控制、run lock、精确 claim。**同一 `_load` 复用仍未证明等价，生产优化不授权**；尤其锁序、并发可见性、completed/saved recovery、异常语义未证。不借测试 GREEN 启动真实 closure。
- 旧真实 attempt 不重发、不手工 `run_definition`；商城源行不读、230 L0 挂起、dev-org 零 canary、m1 单写不 push。

## 第 8/9～9/9 步

本 verification 提交后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立长记忆并读回。下一波 **W5c7p**：先方案，以隔离 PG 针对 claim 的锁序、并发改变、连接/线程/角色身份与完成态/恢复态进行对抗测试；若仍不能证明等价，继续保留原生产读回。
