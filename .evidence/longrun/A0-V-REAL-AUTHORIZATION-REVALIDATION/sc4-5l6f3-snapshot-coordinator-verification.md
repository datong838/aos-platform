# SC4-5l6f3 固定快照协调器验证

日期：2026-09-15
基线：`6e1845c3`
功能提交：`5f3587c7`

## 实现与边界

- 新增 `services/aos-api/aos_api/ecommerce_analysis_snapshot_coordinator.py`。唯一输入是 l6f1 的原 Outbox route；构造时只接受同一原 claims/store 的 `ProductEventAnalysisService`、`PipelineSnapshotGroupCompletion` 和 `EcomConsistencyStore`。
- 协调器逐项复验运行角色、双租户、actor、原 source control/run、installation/generation、accepted occurrence 和唯一 group binding。先在短事务冻结 l6f2 六策略集合，释放锁后执行原组完成，再在新 SERIALIZABLE 事务固定组合 Source、Query、Quality、Business、Brief/Bundle、Readiness、Fulfillment 和统一 snapshot resume。
- 最终提交前重新进入六策略当前守卫；协调期间安装、发布或策略变化会使整个分析事务回滚。调用方不能传阶段引用、策略路径/hash、模型判断或伪造成功结果。
- 已提交重放按 `tenant + exact requirementRef` 派生同一 key，从原统一 Receipt 和唯一不可变 EvidenceBundle item 重建完整命令；原 requestHash、当前 ReadinessPolicy 和 e5c successor 状态全部复验后只读返回，不再次进入旧 Pending 状态。
- 本段不确认、失败或续租 Outbox，不调用 Provider，不授权外部业务写。l6f4 仍须以 Fulfillment + RUNNING AnalysisRuntimeReceipt 双证据完成 Claim。

## Red 与修复证据

1. 有效 Red 先因协调器模块不存在而 collection `ModuleNotFoundError`。
2. 真实 PG 首轮暴露测试组合缺参数化与原 Store 取值错误，只修正测试接线，没有新增产品旁路。
3. 完整执行暴露调用方事务与独立 GroupCompletion 的安装行锁自等待。协调器改为自管短事务冻结策略、独立完成组、最终事务协调并在提交前复验策略；没有放宽安装锁。
4. 测试夹具原 `analysis.connect` 保留外层事务且 `commit` 为 no-op，不能代表生命周期 worker。专项改用同一受限 session identity、`aos_runtime`、双租户 GUC 和 SERIALIZABLE 新连接，数据库调度锁按生产合同通过。
5. canonical JSON 拒绝 tuple tenant，改为明确 `orgId/projectId` 对象；第一次成功后第二次重放证明旧 Pending Owner已关闭，新增统一 Receipt 优先的 committed readback，未让重放重新产生 Evidence 或状态转换。

## 新鲜验证

- 固定协调器专项：`1 passed / 117.14s`。同一用例覆盖首次完整协调、重建协调器只读重放、零新增 Evidence/Readiness/Fulfillment/Host/Store Receipt、route generation 漂移拒绝、当前安装发布策略撤销拒绝。
- 原生完整快照续跑链：`2 passed / 157.60s`。
- 当前安装六策略集合：`7 passed / 32.41s`；此前同波相邻 Owner/编译器回归 `115 passed / 3.87s`。
- 新增/修改 Python 文件 `py_compile` 通过；`git diff --check` 通过。
- `verify_closure.py --phase ar2-7`：`1955 scanned / 195 classified / 93 migrated`，hash、正反依赖、跨层导入和动态引用五类错误均为空。
- Prime/shared-memory：七个强一致投影均为 `CURRENT`，Codex eventual 投影仍为 `PENDING_ASYNC`；`memoryctl validate` 为 `GREEN`，AOS-000573，1201 Delivery / 1183 Task / 2900 Event。

专项仍使用每用例私有全迁移 PostgreSQL、named 商城读取和 named 安装发布资产。它证明原 Owner 的固定组合、事务、幂等和失败关闭逻辑，不代表主库已升级、1.22.0 已真实安装、栖月汇真实数据已自然触发，也不代表八工作台经营场景或连续观察完成。

## 下一项

SC4-5l6f4 新增 `a0v_050` 与受控 Outbox complete/reconcile：当前 Claim、exact Requirement、fulfilled DataFulfillmentReceipt 和 phase=RUNNING 的统一 AnalysisRuntimeReceipt 必须互相绑定且 Lease 仍有效，才允许变为 acked；提交结果不明只能进入 unknown 后严格核对，禁止普通 ack 冒充业务完成。
