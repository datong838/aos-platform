# SC4-5l6e6d2 完整快照组统一收尾验证

日期：2026-09-15
基线：`1460a68c3f2e55a255ca75fbee62f957f85eb82f`（m1 / AOS-000573）

## 实现与边界

新增固定 `PipelineSnapshotGroupCompletion` 宿主服务，内部构造原 Retirement Executor，不接收客户端 success/result/回调。服务以 `org/project/groupId` 派生 PostgreSQL session advisory lock；取不到锁明确拒绝。初始运行状态只负责选择路径：全 running 才执行原 Store 恢复链，全 succeeded 且原执行器已停止才走只读回放，混合、失败或未知状态均拒绝。

原 `qyh_cron_scheduler` 的单路结果保存被最小抽为 `_persist_schedule_result`，事务仍由调用者负责；原 `execute_schedule` 继续调用同一函数并在原位置提交，返回合同、错误脱敏和单路行为不变。完整组服务在独立 Store 效果完成后，以单一元数据事务重新验证原 Assessment/current 权威，锁定十二条 Run 与 Schedule，核对 pipeline/live binding，再用 CAS 写入十二个 succeeded/stopped 终态与 `last_run`。随后在同一事务完成 Projection、Retirement、Audit 原回执后验；任一写入或后验失败时十二路终态和 `last_run` 全部回滚，已提交 Store 效果保留原幂等 Receipt 供恢复。

完成态重放只读取原 Projection/Retirement/Audit 与 Schedule 结果，不调用执行器、不读取源、不改 `last_run/updated_at`。真实 Audit 的缺引用计数继续决定 `complete` 或 `requires_attention`，没有用成功终态掩盖质量问题。执行前、原执行器返回后、逐条终态保存前均检查 deadline/cancel。

## Red、修复与新鲜验证

- Red：新模块缺失，收集阶段 `ModuleNotFoundError`，1 error / 0.52s。
- 第一次组合运行中，原 v1 对象策略被退休 Owner 正确拒绝；测试补为原生 v2 `present-rows-only`，没有修改产品策略守卫。
- 后验首次暴露把 `policy_ref` 误传给 Projection Owner，以及 Projection/Input 层级取值错误；均按原接口最小修正，没有跳过 Owner。
- 最终完整 PostgreSQL 组合：`4 passed, 7 warnings in 179.15s`。覆盖十二路完成及只读重放、第六条终态写入故障整体回滚并依 13 个 Store Receipt 恢复、混合终态不执行、advisory lock 冲突 fail-closed。
- 只读重放补强：`1 passed, 7 warnings in 69.74s`，确认四类 Store 表计数及十二条 Schedule 的 `last_run/updated_at` 均不变，源调用总数仍为 1。
- e6d1 完成态读取回归：`2 passed, 7 warnings in 123.45s`。
- 原 qyh 单路调度回归：`26 passed, 7 warnings in 3.53s`。
- Python 编译与 `git diff --check` 通过。
- `verify_closure.py --phase ar2-7`：`1952 scanned / 192 classified / 93 migrated`，五类错误列表全空。

## 未完成项与下一波

本切片使用完整迁移的 18432 私有数据库和原 Store/Owner，源读取与安装资产 current 仍是明确 named fixture；没有迁移主库、读取真实商城、调用模型、创建真实 Task、安装或发布。它证明完成组收尾和恢复，不证明自然业务首链完成。用户原 `overall-progress-20260913.md`、`package.json`、`package-lock.json` 改动继续保护；不 push，230 L0 挂起。

下一波 e6e 把实际原 Task/TaskRun/Checkpoint/Requirement 初始化、Pending 上下文、十二路完整组统一收尾、快照证据和统一恢复 Receipt 放进同一私有全结构场景，删除剩余 named Pending/stage 拼接。完成后继续开发真实 Outbox 自然消费与安装接线，再进入主升级、栖月汇真实首链、八工作台和连续观察。
