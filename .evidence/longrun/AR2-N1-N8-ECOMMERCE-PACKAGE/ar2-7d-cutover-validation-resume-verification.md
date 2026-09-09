# AR2-7D D5C1 切换验证与恢复权威验证

日期：2026-09-10
基线：`m1@4551b558`
结论：`AR2_7D_CUTOVER_VALIDATION_RESUME_GREEN_ROLLBACK_REMAINS_CLOSED`

## Rules 与实现结论

- 以 closure manifest、231-6 D5、D5C 施工方案为权威；m1 单人串行、先方案后编码、隔离 PostgreSQL、证据后提交；不 push，230 L0 挂起。
- validate 只接受 exact commit Receipt，重验 9/9 extension dispatch、target runtime disabled/fenced revision N+1、paused gate、当前 Approval/Proposal/Draft 以及实际 drain 事实。它只写不可变 `CUTOVER_VALIDATED`/validate Receipt，不调用 handler、Provider 或真实源。
- resume 只接受 exact validate Receipt。固定 SECURITY DEFINER 函数再次核对数据库权威，在同一事务内把 runtime 推进到 enabled/unfenced revision N+2、把 gate 推进到 open revision 2，并把 operation 推进为 resumed；Python 随后回读 9/9、runtime/gate 并写 `CUTOVER_RESUMED`/resume Receipt。
- validated/resumed 状态受 deferred history guard 约束。直接调用 resume 函数但不写 resume Receipt 时，提交失败且 runtime、gate、operation 全部回滚。
- 本切片只关闭成功出口；验证窗口失败时仍保持 D5B 的 runtime/gate 双重关闭。新的 rollback operation、dispatch fence 和 9/9 legacy 恢复在 D5C2，未用手工 UPDATE 冒充回滚。

## 文件与方案一致性

- `services/aos-api/alembic/versions/ar2_015_ecommerce_growth_cutover_finalize.py`：扩展状态、事件和 phase 枚举，新增 resume 受限函数与 validate/resume 延迟历史门；空权威可降级，有 finalize 权威时拒绝降级。
- `services/aos-api/aos_api/ecommerce_growth_cutover.py`：新增严格 finalize 请求/Receipt、commit/validate exact ref 链、当前审批重验、final state 读回与稳定 replay。
- `services/aos-api/tests/extension_runtime/test_ecommerce_growth_cutover_pg.py`：接续 ar2_015，验证 validate/resume 正反例、三类权威漂移、直接函数回滚、Receipt 漂移和 downgrade 门。

## 验证证据

- D5A～D5C1 cutover 与 occurrence PostgreSQL 专项：`34 passed, 7 warnings in 10.07s`。
- Router/Host/occurrence 邻接：`39 passed, 7 warnings in 3.36s`。
- 完整 `tests/extension_runtime` 串行复跑：`741 passed, 503 skipped, 7 warnings in 19.31s`。
- Alembic 单一 head：`ar2_015`。
- Closure：`1708 scanned / 93 classified / 57 migrated`，五类错误数组均为空。
- Memory validate：`AOS-000571 / GREEN / 865 Delivery Receipts / 2226 events / 846 Task Receipts`。
- Python compile 与 `git diff --check`：通过。

## 关键反例与运行轨迹

- dispatch 单行 revision、runtime revision 或 gate revision 任一漂移，validate 均失败关闭。
- commit Receipt content hash 漂移拒绝；validate 与 resume 相同请求分别稳定回放原 Receipt。
- resume 后 runtime 为 enabled/unfenced revision 15、gate 为 open revision 2；同一 pending occurrence 才能被 claim。
- maintainer 直接调用 resume 函数但缺 resume Receipt，在 deferred constraint 提交点失败；回读仍为 validated、runtime fenced、gate paused。
- 首次把完整 extension_runtime 与邻接套件并行执行，两个测试进程同时修改全局 `aos_runtime` 角色，PostgreSQL 报 `tuple concurrently updated`，属于共享角色 DDL 的测试基础设施竞争，未计入产品失败。停止该轮后串行复跑全绿；后续该全量套件保持单进程串行。

## 内容摘要与保留边界

- `ecommerce_growth_cutover.py` SHA-256：`4b1575475547756af3f38067eee3425bb2b5b62a3e895094f2201ac7080cc53c`
- `ar2_015` SHA-256：`50c2dd31dcb7fdaf0913aef77c2acf4b26d1a8c193a119bb3073eae3cc0c854f`
- 未执行真实 cutover、真实租户写入、共享/生产迁移、真实源读取、Provider、费用、发布或 push。D5C2 rollback、D6 lifecycle 与 7E/A0-V 仍未封板。
