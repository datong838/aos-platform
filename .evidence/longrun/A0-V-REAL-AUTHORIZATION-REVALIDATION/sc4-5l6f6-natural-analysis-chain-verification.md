# SC4-5l6f6 原事件到 worker 自然续跑与重建恢复验证

日期：2026-09-15
基线：`7880fbc7`
实现提交：`ad13298e`

## Rules 与方案范围

- 先复核产品目标、`snapshot-resume-design.md` 和 l6f1-l6f5 原实现，再写 l6f6 方案、preHash 与退出条件；真实 Red 暴露生产缺口后先补方案再改产品代码。
- m1 单写者串行；仅修改本波精确文件，不触碰用户进度文档、package 文件或其他脏文件，不 push，230 L0 继续挂起。
- 保留原安装、租户、RLS、幂等 Receipt、预算/审批和 unknown 失败恢复边界；测试不得手工写入成功结果或放宽 exact ref。
- 代码后必须做新自然链、原路径回归、AR2 清册、Prime 投影和风险/方案一致性检查。

## 实现与真实 Red 修复

- `test_analysis_snapshot_resume_chain_pg.py` 增加 `natural-worker` 夹具模式：由真实已领取 ProductEvent occurrence 经 `ProductEventConsumptionWorker._dispatch` 调用原 `ProductEventAnalysisService.handle_with_data`，自然生成初始 Analysis Receipt、DataRequirement 与 Outbox；随后不手工创建 Evidence、Fulfillment 或 Resume Session。
- 新增 `test_analysis_data_requirement_natural_chain_pg.py`，只调用生产 `AnalysisDataRequirementWorker.tick()`。隔离库使用完整迁移、十二源原生组、真实 Store/Projection、固定六策略、Query binding、Task/Run/Checkpoint、双 Receipt 数据库门和正/负租户。
- 首次自然链将原 TaskRun 从 `paused` 恢复到 `running`，业务 Run 从 `WAITING_DATA` 进入 `PREPARING`；Delivery 为 `acked` 并保存 Fulfillment 与 RUNNING Analysis 两张 exact Receipt。第二次 tick 空闲且业务状态、版本、内容哈希和计数不漂移。
- 重启用例在协调器已提交后模拟 `complete` 响应丢失，使 Delivery 成为 `unknown`；再过期原 Lease、销毁并重建 Worker。重建后先处理原 unknown，复用同一 attempt/token，以只读重放取得原双 Receipt并完成 `acked`；没有新 claim 或第二套业务副作用。
- 真实 Red 发现 `AnalysisDataRequirementRouteReader` 在统一恢复 Receipt 已存在时，会按同 Run 同时读到原 `PREPARING` 和后继 `RUNNING` Receipt而拒绝重建。产品修复只在原查询中加入既有根语义 `phase=PREPARING / completed=false / requirementRef=null`，随后仍执行原完整 Run、Case、cutoff、hash、Occurrence 和 current Requirement 校验；不按时间猜测、不接受后继 Receipt。

## 新鲜验证

- 自然首次续跑：`1 passed / 97.88s`。
- 提交未知后的 Worker 重建、过期 Lease 恢复：`1 passed / 106.52s`。
- 原 Route 完整 PG 回归：`2 passed / 155.04s`。
- 原统一续跑组合正反回归：`2 passed / 165.46s`。
- Worker 与 Outbox 快速累计回归：`19 passed / 9.10s`。
- `py_compile`、`git diff --check` 通过。
- AR2 `verify_closure.py --phase ar2-7`：`1956 scanned / 196 classified / 93 migrated`；hash、正反依赖、bundle 跨层导入、动态引用五类错误列表均为空。
- Prime/shared-memory：七个强一致投影均为 `CURRENT`，Codex eventual 投影为 `PENDING_ASYNC`；`memoryctl validate` 为 `GREEN`，AOS-000573，1201 Delivery / 1183 Task / 2900 Event。

## 一致性、风险与限制

- 与 l6f6 方案一致：测试入口止于真实 ProductEvent dispatch 与生命周期 Worker tick，DataRequirement、十二源完成、Evidence、Readiness、Fulfillment、状态转换和双 Receipt均由原 Owner/生产协调器生成。
- canary `dev-org/dev-project` 在两条自然链结束时均无 Delivery、Requirement、业务 Run 或 Evidence；正租户查询仍通过运行角色、GUC 与 RLS。
- 根 Receipt 查询更窄，且保留结果唯一性与全字段复验；若未来根阶段合同改变为非 `PREPARING`、非 JSON null，路由会失败关闭并要求显式迁移，不能误选后继结果。
- 本波使用每用例独立完整迁移数据库，以及具名的安装资产、商城源与 Provider 健康边界。它证明代码的自然编排与故障恢复成立，不代表主运行库已经升级，也不代表栖月汇真实数据、模型分析、人工评审和八工作台经营场景已经执行。

## 下一波

SC4-5l6g 先核主运行库、API/前端/Runtime Host 与当前安装权威，形成可回滚执行清单；再在正租户完成主库精确升级、领域包安装/配置/禁入/恢复/卸载重装演练。每个控制动作读取实际 Receipt 和数据库状态，canary 同步验证。控制面通过后进入真实栖月汇 ProductEvent 首链与八工作台经营计划执行；测试 GREEN 不替代真实业务观察和发布决定。
