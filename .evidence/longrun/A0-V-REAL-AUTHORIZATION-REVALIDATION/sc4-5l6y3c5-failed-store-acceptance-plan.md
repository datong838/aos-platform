# Y3c-5 全停止失败到原Store完成验收（C4后实施）

## 验收结果 2026-09-16

新增stopped-failed完整主例通过：1 passed，827.75s（13分47秒），7项既有依赖警告；日志 `/tmp/aos-failed-store-acceptance.log`。运行使用18434隔离PG和原实际Store；没有运行第二套PG测试，也未迁移/重启主服务。原running主例已有773.65s通过证据，本次不重复。

原普通Completion写入1对象/1Receipt后模拟确认丢失；明确停止失败fixture及正式续期后，经原Completion锁内十二原Run原子重领、实际Store/Link/投影/retirement到十二succeeded/stopped。最终12对象、12DatasetReceipt、13StoreReceipt、1Link；原SourceClaim/Run仍各12，原恢复claim恰好12。新实例完成重放后计数、projection/preparation hash及恢复claim标识/hash不变，源调用总数1。方案与断言对账通过，diff检查通过；本波无新增生产逻辑，不制造Red记录。

性能未验收，源/安装资产仍具名夹具，真实经营链未完成。下一波按 `sc4-5l6y4-managed-worker-implementation-plan.md` 的Y4a–Y4d顺序补周期派发、受管理执行、停机/状态、恢复请求与页面，再接Y5/Y6/Z。m1不push、230 L0挂起。

前置C4原子重领及原普通Completion回归通过后，扩展tests/extension_runtime/test_snapshot_group_recovery_runtime_pg.py主例为running与stopped-failed两路。只运行新增失败路，不重复已通过的773秒running路，除非新的失败说明两路都需再验。

真实隔离源input一次，原普通Completion提交1对象/1Receipt后确认丢失；具名隔离fixture将原十二Run标为failed/明确stopped/finished，正式C2c审批新窗口，C3c Runtime在原Completion锁下经C4原十二Run重领，再走实际Store/投影/Link/retirement/终态。验证新增恰好12条原ecommerce_ingress_recovery_claim，原Run与SourceClaim仍12，无新组，无源重读。

最终必须与running路同业务事实：12对象、12DatasetReceipt、13StoreReceipt、1Link、12succeeded/stopped；新的Runtime/连接completed重放保持所有数量和projection/preparation hash，原recovery claim哈希也不变。只把真实PG/Store和原Owner链标为已验，源/安装资产仍夹具，主库与真实首链未完成。

完成后复核C1–C5方案代码一致性、整合施工清单，再接Y4 worker/停止生命周期和服务端运行状态，Y5十二路真实业务配置，Y6克隆迁移/主服务运行与Z业务Run恢复。恢复执行HTTP/前端与工厂应与Y4实际worker路径统一，不能分别造一个不受运行管理的后台线程。
