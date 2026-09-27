# W5CB4 D01 C2b1：正式原 Task/Plan 到 D01 可发行态（2026-09-27）

## 上位与目标

承接 231/231-9 A1 首链、C2b 同库联合正向计划及 C2b0 审计。正式 AnalysisRuntimeReceipt 的原 TaskRun 在初始化后是 `paused`；D01 原 Issuer 必须读到当前 `running` Run、`executing` Task、正式批准且三阶段 Schema 样式 Plan。先用真实 AIP Task Owner 的审批/恢复合同证明原链能合法到达这些状态，不通过直接 SQL 改状态，也不接 Provider/Host。此切片不声称 AgentRun Owner/完整 C2b 通过。

## 文件级清单与九步

1. 复习 `ecommerce_analysis_continuation_origin.py`、`aip_task_store.py` 的 approve/resume 与 231-9 BG-03 方案，以及 `test_analysis_initial_checkpoint_pg.py`、`test_product_event_analysis_bootstrap_pg.py` 正式夹具。
2. 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_analyst_d01_formal_ready_pg.py`：先 RED 读取原 Receipt/Task/Plan 状态，尝试经原 Owner 审批/初始 checkpoint resume 到 D01 预检；无批准/Plan 漂移/旧 Run 必须拒绝。
3. 若现有 Owner 合同不能合法支持该路径，先在本计划标明真实阻点，最小修 `services/aos-api/aos_api/ecommerce_analysis_task_preparation.py` 或相关原 Owner；不能更改 `NaturalD01Issuer` 的门。
4. 专项与原链/D01/Task 累计；安全浏览器只读禁入；代码/方案复审、verification、m1 提交、上下文更新后继续 C2b2 来源/Owner 联合正向。

## 边界

仅隔离 PG；不读取商城源、不迁当前 a0v_106、不激活 18181/worker/Provider、不重放旧 Run。未知提交原 key/Receipt 只读对账；不能以测试 fixture 直写 `aip_task_run.status` 冒充正式恢复。若此路径已经存在，只写证明和最小测试，不发明新运行器。

## 执行中裁决（2026-09-28 00:02 +08:00）

正式 Plan 已批准且是三阶段 Schema-only，真实 TaskRun 确实暂停；通用 `AipTaskStore.resume_run` 被 `ANALYSIS_BOOTSTRAP_CONTINUATION_AUTHORITY_REQUIRED` 正式拒绝。现有专用 `_AnalysisDataResumeSession` 在缺真实 fulfillment 时也拒绝；`_AnalysisSnapshotResumeSession` 的正向测试明确标注 named snapshot stage fixture，不是十二来源真实验收。因此 C2b1 不得靠代码弱化原 Owner 取得正向。此切片收为**已验证负向前置、正向未过**，及时把实际可做的 BG-00 正式配置和其他独立产品入口前移；原 C2b1 正向在满足真实 readiness 后重启。
