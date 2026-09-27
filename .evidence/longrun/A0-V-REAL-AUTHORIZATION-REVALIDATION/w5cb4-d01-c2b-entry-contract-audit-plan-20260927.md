# W5CB4 D01 C2b0：联合正向前置合同有界审计方案（2026-09-27）

## 目标与范围

按 231/231-9 首链和 `w5cb4-d01-c2-full-owner-joint-proof-plan-20260927.md`，只读核现有正式原链 fixture、真实 D01 选择隔离 PG 和 AIP AgentRun Owner 的可拼接前置。判定能否在本波合理构造一次真实同库正向；不能则精确列缺口、保留 C2b 未通过，并先做 BG-00 首链合法绑定主线，不把 fake/空库测试冒充自然成功。

## 文件级执行

1. 复核 `test_product_event_analysis_bootstrap_pg.py`、`test_analysis_continuation_origin_pg.py`：正式 `formal_case` 的真实 TaskRun 状态、原 AnalysisRuntimeReceipt 阶段与原 SourceSelection。
2. 复核 `test_ecommerce_analyst_d01_source_selection_pg.py` 的正式 Schema 两阶段选择；`ecommerce_analyst_d01_atomic.py` 与 `aip_agent_run_service.py` 的同事务输入和当前实例/Skill/Logic/Capability 门。
3. 专项重跑已有真实原链与选择 PG 测试，核最近 108 项累计；只作安全预览禁入浏览器检查，不往当前业务库写夹具。
4. 落本波审计 verification，列 C2b 精确恢复入口与 BG-00 文件级下一波；本审计不改生产代码、不放松任何门。

## 停止/退出

若最小联合 fixture 仍需另行构造从 `paused`→`running` 的正式 Task/Plan 审批，以及 active AgentInstance、published Skill/Logic、active binding 与健康 Capability，则 C2b 正向保留待办，转 BG-00。不得通过修改正式 Owner 或原链来让测试假绿；当前实例 a0v_106 不迁移。
