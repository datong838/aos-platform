# SC4-5l6f5 生命周期固定 DataRequirement worker 验证

日期：2026-09-15
基线：`1e5812f1`

## 实现与边界

- 新增 `services/aos-api/aos_api/ecommerce_analysis_data_requirement_worker.py`。worker 只枚举 App 生命周期 `LivePreparedJobDirectory` 中当前安装的 tenant scope，每轮最多处理四个 scope；没有 live 目标时不读取 Outbox。
- 每个 scope 先读取一条原 `unknown` attempt 做严格恢复；没有 unknown 才领取一条 `data.requirement.request`。正常路径固定执行 Claim → immutable Route → 当前 live installation/generation → 当前 actor membership/markings → 生产工厂构造原 Analysis → 固定 Snapshot Coordinator → 双 Receipt complete。
- 扩展 `DataRequirementOutboxStore.read_unknown_next` 和 `AnalysisDataRequirementRouteReader.read_unknown`。恢复保留原 attempt/token，允许 Lease 已过期，但仍逐字段核 Outbox、Requirement current head、PREPARING root Analysis Receipt、event occurrence、ProductEvent origin 和 snapshot group；unknown 不能走普通 claimed 入口。
- `PipelineControlServiceFactory.build_analysis_snapshot_coordinator` 从 route 重建原 source journal、domain/growth 当前安装 invoker、同一 source-claim Owner、`EcomConsistencyStore`、完整组 Completion 和 phase5 engine。调用方不能传 success、Fulfillment 或恢复 Receipt。
- App 只在 Extension Runtime Host 为 ACTIVE 时创建 `analysis-data-requirement`，与 Host、ProductEvent worker 共用 stop event 和 host-ready 条件。异步取消会等待线程内同步事务完成，再传播取消。
- 协调器调用前的 route/current-installation/actor 拒绝可确定为零业务副作用，置 failed；进入协调器后的任何异常或 complete 结果不明只尝试置 unknown。若 complete 实际已提交或 Lease 已过期，数据库围栏拒绝错误改写，保留 acked 或可重新领取的原状态。

## 新鲜验证

- worker、原 ProductEvent worker、App 生命周期、Outbox Store 快速回归：`45 passed / 6.22s`。覆盖空目录零动作、正常双 Receipt 完成、unknown 优先恢复、协调前 failed、协调/complete 后 unknown、unknown 失败不改写、四 scope 上限与轮转、取消等待、ACTIVE 生命周期拥有及既有生命周期回归。
- 独立完整迁移 PG 的 route 与生产工厂组合：`3 passed / 230.59s`。其中原 route 正向在真实 Delivery 上转 unknown 后，以相同 attempt/token 跨过 Lease 过期重建相同 route；普通 claimed 入口拒绝；当前 Requirement 头漂移拒绝；工厂组合保持原 source-claim Owner。
- 完整 Snapshot Coordinator 累计回归：`3 passed / 319.74s`。正常 complete、unknown reconcile 和生产工厂组合全部通过；十二源组完成、Source/Quality/Business Evidence、Bundle、Readiness、Fulfillment、统一 Run 恢复与双 Receipt 数据库门保持一致。
- Python `py_compile` 和 `git diff --check` 通过。
- AR2 `verify_closure.py --phase ar2-7`：`1956 scanned / 196 classified / 93 migrated`；hash、正反依赖、bundle 跨层导入和动态引用五类错误均为空。
- Prime/shared-memory：七个强一致投影均为 `CURRENT`，Codex eventual 投影为 `PENDING_ASYNC`；`memoryctl validate` 为 `GREEN`，AOS-000573，1201 Delivery / 1183 Task / 2900 Event。

## 一致性与风险复核

- 与方案一致：worker 没有新公开 API、全租户目录扫描、客户端成功声明或模型选择控制流；当前安装被禁用、替代或停止后，目录解析/Invoker admission 会失败关闭。
- 数据库运行角色仍只经既有函数转换 Delivery，没有获得 Delivery、Outbox、Fulfillment 或 Host Receipt 的直接 DML 权限；canary scope 不在正租户 live 目录时零触达，scope SQL 仍受 RLS/GUC 限定。
- unknown 读取本身不加第二把领取锁；并发恢复由 snapshot-group advisory lock、各 Owner 幂等键和 Delivery 行锁收口。竞争者可能本轮返回 unknown，后续轮询继续，不会产生第二套 Task/Run/Receipt。
- 当前专项使用完整隔离迁移库与 named 安装/源/Provider夹具。它证明固定 worker 和 App 接线代码成立，不代表主库已升级或真实栖月汇 ProductEvent 已由启动后的进程自然跑完整链。

## 下一项

SC4-5l6f6 删除测试调用方对 route/coordinator 的手工接线：从原 ProductEvent worker 产生 DataRequirement Outbox 后，只调用生命周期 worker tick；覆盖首次自然续跑、协调前崩溃、协调提交后 complete 前崩溃、进程重建恢复、Lease 过期、新旧安装代次、canary 隔离和二次 tick 零新增副作用。完成后进入 l6g 主升级/安装与真实栖月汇首链验收。
