# W5CB4 D01 Task／原链 SourceSelection 一致性门（2026-09-27）

## 边界与结论

- 方案：`w5cb4-d01-current-packet-selection-plan-20260927.md`，本子波只处理已创建 Task 的 `selectionRef` 与原 AnalysisContinuationOrigin `context.source.policy.sourceSelectionRef` 的身份、修订一致性。
- `NaturalD01AtomicCoordinator` 在原 `run_current` 回调和同一 serializable 事务内读取 Task timeline，先要求原选择为 exact `SourceSelectionRevision`，再核 Task 引用的 ID、修订和 PostgreSQL 权威。缺失、错 ID、错修订都在 AgentRun Owner 写入及 commit 前失败关闭。原 exact 哈希仍由原 SourceSelection Owner 复核，本子波不建立第二来源权威。
- 该 coordinator 仍未注册 Host；不代表 Method／Metric／Query／EvidenceBundle／DisclosureGrant 完整 D01 packet 已被正式选择，也不代表预算、模型、Skill、Capability、Provider 或自然首链可运行。没有业务库写、商城源读取、旧 Run 重放、手工 `run_definition`、Provider 调用或外部效果。

## 可复核证据

1. RED：新添错 ID／缺失 Task selection 的 2 项测试均按预期失败（未抛 ValueError）。后续加错修订负例，共 3 项门禁负例。
2. GREEN：`uv run --directory services/aos-api pytest -q tests/extension_runtime/test_ecommerce_analyst_d01_atomic.py tests/extension_runtime/test_ecommerce_analyst_d01_issuer.py tests/extension_runtime/test_analysis_continuation_origin_pg.py tests/extension_runtime/test_analysis_task_preparation_pg.py tests/aip/test_aip_agent_run_execution_service.py --tb=short`：60 passed、7 既有 warnings。
3. `git diff --check` 无问题；当前安全预览 8434 HTTP 200，8080 根路径 404（端口可达但该路径无路由），18181 无监听。此代码未接到预览路由，浏览器交互验收不适用，绝不以端口状态冒充运行验收。
4. 复审：只在原链通过后的同事务加一项只读 Task 比较；没有改 Task 表、Owner Receipt、准入判定或已运行实例。异常直接传播，无 retry／重发。

## 下一波

先追正式批准来源 Owner 是否已持有同 TaskRun、同截止面、可撤销的 D01 完整 packet 选择；若无，先形成窄 `D01SourceSelection` 合同和同租户持久化／CAS／幂等 Receipt 方案，再写 RED 和最小实现。不能以当前库“最新一条”、调用者任意 packet 或测试 fixture 充当当前选择。BG-00 当前安装配置与首链最小绑定另行并行排优先级；Host／Provider 保持关闭。
