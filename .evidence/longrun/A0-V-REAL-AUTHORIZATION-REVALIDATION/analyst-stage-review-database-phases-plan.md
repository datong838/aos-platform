# Analyst stage review 数据库三阶段适配方案

日期：2026-09-12  
基线：`aa6d7d35`  
状态：APPROVED_FOR_IMPLEMENTATION（用户已授权 m1 串行持续开发，不 push）

## 目标

把阶段评审协调器的抽象 `prepare` / `commit` 落成可验证的数据库边界：准备阶段在第一笔短事务内固定授权快照和最多四个校验交换，事务关闭后才调用已安装 Growth 包；所有 IPC 成功且 prepared 未漂移后，第二笔短事务重新读取当前授权快照，exact 相等时才发布阶段评审结果。

本切片不接入具体 ORM 表、不改变现有 `StageReviewCommand` 写路径、不升级或重装 `solution.ecommerce.growth@1.4.0`。它只提供宿主数据库阶段适配器，后续由 owner-specific builder/publisher 绑定真实模型。

## Rules

1. 两笔事务必须由同一显式 `transaction_factory(command)` 分别创建；不得跨 IPC 保留连接、游标或锁。
2. `prepare_in_transaction`、`load_current_snapshot`、`publish_in_transaction` 必须是同步、短事务回调，事务体内不得出现 await。
3. prepared 必须绑定原命令 canonical hash、非空原生 JSON authority snapshot、一至四个 kind 唯一交换；构造后任一层发生修改都 fail closed。
4. IPC 只由既有 one-shot port 执行。拒绝、超时、取消、返回漂移等未知结果直接上抛，不重试，不进入第二笔事务。
5. commit 使用新事务读取 current snapshot；只有 canonical JSON exact 相等才可调用 publisher。漂移时不得发布。
6. publish 与第二次 current 检查处于同一事务；publish 异常交给事务上下文回滚，禁止自动重放 IPC 或 publish。
7. 为避免调用任务取消后后台线程仍继续发布，适配器使用 async 接口但同步完成每个有界事务段，不把 commit 投递到后台线程。
8. 不触碰现有数据和 Installation，不 push，不纳入无关未跟踪文件；230 L0 继续挂起。

## 变更文件

- `services/aos-api/aos_api/ecommerce_analyst_stage_review_coordinator.py`
- `services/aos-api/aos_api/ecommerce_analyst_stage_review_database_phases.py`
- `services/aos-api/tests/extension_runtime/test_analyst_stage_review_coordinator.py`
- `services/aos-api/tests/extension_runtime/test_analyst_stage_review_database_phases.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/analyst-stage-review-database-phases-plan.md`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/analyst-stage-review-database-phases-files.json`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/analyst-stage-review-database-phases-verification.md`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md`

## 验收条件

1. 集成测试观测到严格顺序：事务一 open/prepare/close → IPC → 事务二 open/reload/publish/close；IPC 期间活跃事务数为零。
2. current snapshot 漂移时 publisher 调用数为零；第二笔事务正常退出且不泄漏资源。
3. IPC 未知结果时只出现第一笔事务，第二笔事务和 publisher 均为零。
4. publisher 异常由第二笔事务收到并回滚，所有 IPC 与 publish 均只调用一次。
5. 非 JSON/空快照、异步事务回调、结果数量不匹配、prepared 或 exchange 修改全部 fail closed。
6. 定向测试及相关阶段评审回归通过，验证文档与清册记录实际 SHA256、边界和下一项。

## 风险与后续

- 同步事务段会短暂占用事件循环；这是当前同步数据库栈下为消除后台发布未知结果而作的有界选择。真实 builder/publisher 必须保持查询和写入短小。
- 此适配器无法单独证明真实 owner/tenant/lease/current 语义；下一波应实现 owner-specific authority snapshot builder 与 publisher，再接入现有 `StageReviewCommand` 路径。
