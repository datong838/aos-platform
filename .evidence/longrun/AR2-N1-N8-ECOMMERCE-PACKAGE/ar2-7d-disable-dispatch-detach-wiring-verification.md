# AR2-7D D6A2 停用与 dispatch 解绑生产接线验证

日期：2026-09-10
基线：`m1@144dfe03`
结论：`AR2_7D_DISABLE_DISPATCH_DETACH_WIRING_GREEN`

## Rules 与实现结论

- 以 closure manifest、231-6 D6、D6 施工方案和 D6A1 已提交 authority 为准；m1 单人串行、最小接线、隔离验证、证据后提交；不 push，230 L0 挂起。
- `begin_disable` 在既有 `RuntimeBindingStore.fence` 后、同一事务提交前调用 `after_runtime_fenced`；hook 失败时 runtime fence 与 dispatch lifecycle 一并回滚。
- `finish_disable` 在既有 runtime operation 推进到 `succeeded` 后、同一事务提交前调用 `after_runtime_disabled`；hook 失败时第二事务整体回滚，第一事务已提交的 runtime/gate/dispatch fence 保持有效。
- service 的预取消 fence、executor 的两事务执行、consumer 恢复执行都传递同一个 dependent。没有 dependent 的测试/复用构造保持原 no-op；生产 worker dependencies 和 control plane 必须构造精确 `EcommerceGrowthDisableDependent`。
- terminal outbox 重投只 ack，不重新执行 dependent；普通非 ecommerce disable 因 D6A1 查不到 resumed activation而保持 no-op。

## 修改文件

- `services/aos-api/aos_api/extension_runtime/disable_commit.py`
- `services/aos-api/aos_api/extension_runtime/disable_executor.py`
- `services/aos-api/aos_api/extension_runtime/disable_service.py`
- `services/aos-api/aos_api/extension_runtime/disable_consumer.py`
- `services/aos-api/aos_api/extension_runtime/production_runtime.py`
- `services/aos-api/aos_api/asset_registry/control_wiring.py`
- `services/aos-api/tests/extension_runtime/{disable_case.py,test_ecommerce_growth_cutover_pg.py,test_production_runtime.py,test_runtime_host_directory_pg.py}`
- `services/aos-api/tests/asset_registry/test_control_wiring.py`

修改与方案一致：只扩展既有 disable 依赖传递和两个事务边界，不复制状态机、不改变 drain 判定、不增加 handler 或外部调用。

## 验证证据

- D6A concrete 两事务、两类 hook 回滚专项：`3 passed, 51 deselected, 7 warnings in 3.78s`。
- 完整 ecommerce cutover PostgreSQL：`54 passed, 7 warnings in 15.02s`。
- disable/lifecycle/production/control/role-directory 邻接：`116 passed, 7 warnings in 17.74s`。
- signed installation 全流程及 dependent 顺序断言：`33 passed, 9 skipped, 7 warnings in 17.56s`。
- 完整 `tests/extension_runtime` 串行：`1238 passed, 28 skipped, 7 warnings in 82.90s`。
- Alembic 单一 head：`ar2_017`。
- Closure：`1709 scanned / 93 classified / 57 migrated`，五类错误数组均为空。
- Memory validate：`AOS-000571 / GREEN / 865 Delivery Receipts / 2226 events / 846 Task Receipts`。
- Python compile 与 `git diff --check`：通过。

## 失败注入与风险复核

- fence hook 在完成 D6A1 写入后抛错：runtime operation 回到 accepted，binding 仍 enabled/ready，lifecycle 行为 0。
- detach hook 在完成 D6A1 写入后抛错：runtime operation 仍 running/fencing，binding 仍 disabled fence/draining，lifecycle 保持 fenced；没有伪造 succeeded 或 legacy 恢复。
- 预取消 service 路径只调用 fence；executor 完成时只补 disabled。普通 consumer 调用 fence/disabled 各一次；terminal redelivery 不重复调用。
- 一次误并行启动两套 PostgreSQL 全局迁移夹具，因同时 ALTER 测试角色触发 `tuple concurrently updated`；业务断言未开始。随后恢复严格串行并从头通过完整 cutover、邻接与全量门。
- 未执行真实租户停用、真实 dispatch、共享/生产迁移、真实源读取、Provider、费用、发布或 push。D6B/D6C/D6D 仍待施工。

## 关键内容摘要

- `disable_commit.py` SHA-256：`592e84391a29d91ef83250975261cd6f8533fd6a5689fb1b08e438a3333bcd96`
- `production_runtime.py` SHA-256：`68a38dfab0c4d9db454abc1abcc195fa08eb7dd5a73f2939e5c117f186bd788e`
- `control_wiring.py` SHA-256：`2a22da5725a629e3d90289d702f88d0a77ee2340bf668a18c4eb29173c10d16e`
- `test_ecommerce_growth_cutover_pg.py` SHA-256：`db1b4ebf1f6c43378ae803992963b1467642ebfed008a9ba17052a488de4f293`
- `disable_case.py` SHA-256：`47f98722478599ad055296017d7c88c96cbcf290bbc893f6f42264ae31b51f25`
