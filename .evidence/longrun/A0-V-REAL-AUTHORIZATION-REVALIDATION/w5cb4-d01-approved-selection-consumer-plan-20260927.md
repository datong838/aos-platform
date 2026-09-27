# W5CB4 D01 C：同事务批准选择消费者方案（2026-09-27）

## 上位方案与现场

承接 231 A1-02/03、231-9 BG-02/03 和 `w5cb4-d01-complete-packet-selection-plan-20260927.md`；A `088fe0eb` 是候选合同，B `ce18aa32` 是隔离库 append-only 决策 Owner。当前真实预览库最近证据仍是 a0v_106，C 仅可在隔离测试库验证，不能注册 Host 或宣称当前实例已选包。

`NaturalD01AtomicCoordinator` 已把原 AnalysisContinuationOrigin、Task、D01 来源和 AgentRun Owner 放在同一 serializable 事务，但仍接受外部 packet。故 C 必须在 Owner 写前读取同 Run/Plan 的**唯一有效批准选择**，并要求外部 packet 精确等于不可变提案；没有批准、已有撤销、跨租户、错原 Plan/Run/SourceSelection、hash 漂移均 fail closed。旧 proposal 不得成为当前 Plan/Grant 的永续授权。

## 文件级最小改动与 RED

1. `services/aos-api/aos_api/ecommerce_analyst_d01_source_selection_store.py`：补 `read_current(transaction,scope,task_run_id,plan_id,actor,occurred_at)`，只按原唯一 Run/Plan 读 proposal、approval、revocation，重算提案 hash/request hash，重读 TaskRun/Task/Plan 当前批准与 SourceSelection，校 checker/Receipt/时间与未撤销；返回批准的 `D01SourcePacket` 和决策 Receipt，不自行 commit。读不到或多义直接拒绝。来源 Method/Query/Bundle/Grant 的当前性继续由 `require_current_d01_sources_in_transaction` 在同一事务执行，不在选择表重复缓存正文。
2. `services/aos-api/aos_api/ecommerce_analyst_d01_atomic.py`：在 `origin.run_current` 的回调内先读 `read_current`，校 packet 精确值，再交原 `NaturalD01Issuer` 与当前来源读取器；未知 commit 边界保持原键只读对账，不重发。
3. `services/aos-api/tests/extension_runtime/test_ecommerce_analyst_d01_selection_store.py`、`test_ecommerce_analyst_d01_atomic.py`、`test_ecommerce_analyst_d01_source_selection_pg.py`：先 RED 覆盖无批准、撤销、hash 漂移、scope/Plan/Run 漂移、外部 packet 漂移与原 Owner 零写；隔离 PG 正向必须从 B 的真实两阶段决策读取到同一事务 Owner Receipt，不能把 fake 当正向门。

## 验证、退出、停止

专项→D01/原链/Task/AgentRun 累计→安全浏览器现状→方案/代码复审→verification→m1 精确 commit→D 波。C 不迁移当前库、不碰商城源数据、不开放 18181/Host/Provider；若独立 PG 正向无法合法构造，不以 mock 或旧 Run 代替，记录窄边界并继续 BG-00 可独立工作。当前库迁移前仍须独立备份与身份/版本回读。用户既有测试文件和 w5c8i 文件不改不提交。

实施分界：**C1** 是批准选择当前读门与 Atomic 接线，要求真实隔离 PG 决策正向/撤销负向和 Atomic Owner 零写负例；**C2** 才是完整原 AnalysisContinuationOrigin→批准选择→当前 Method/Query/Bundle/Grant→AIP AgentRun Owner Receipt 的隔离 PG 联合正向。C1 可独立提交 verification，但不得把它记作 C 总门完成或 D 当前库迁移许可；C2 在 D 前补齐。这样不因构造全链夹具延误已可复用的 fail-closed 读门。
