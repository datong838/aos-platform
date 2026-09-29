# W5CB4 BG-00ax｜C2b 原链合法夹具审查

方案：`w5cb4-bg00ax-c2b-legal-fixture-audit-plan-20260929.md`。本波只读代码/既有证据，未调用 Host、Provider、商城源或旧 Run，也未写当前库。

1. C2 总方案要求真实 `AnalysisContinuationOrigin` + 正式 Schema Plan + 同一 checker 独立批准 exact 后置 packet + 当前 Method/Eval/Metric/Query/EvidenceBundle/Grant + AIP AgentRun Owner，在同一隔离 PG 事务得到唯一 Receipt。现有 `ecommerce_analyst_d01_atomic.py` 是未注册的 coordinator，只有 `test_ecommerce_analyst_d01_atomic.py` monkeypatch 的 unit 正向；没有 `test_ecommerce_analyst_d01_atomic_pg.py` 联合正向文件，不能把 mock callback 当 C2b。
2. C2b1 已有真 PG 负向：正式编译 Plan 三阶段 inputRefs 是 schema，原 TaskRun `paused`；普通 AIP Task Owner resume 被 `ANALYSIS_BOOTSTRAP_CONTINUATION_AUTHORITY_REQUIRED` 拒绝。`_AnalysisDataResumeSession` 强制原 Receipt、同一事务和当前来源会话；无 fulfillment 不可由直接 Task 状态写入绕过。`test_analysis_snapshot_resume_states_pg.py` 的正向明确以 `named_snapshot_current` monkeypatch 整个 snapshot stage，并在注释声明不是十二源证明。
3. 当前没有合法原十二源 fulfillment/专用恢复会话与正式配置绑定，不能仅凭现有 fixture 构建 C2b PG Owner 正向。此前 C2b1 专项3 passed/相邻109 passed 是控制面负向证据，不是今天的新运行或业务成功。本波未新增“正向”测试，以免伪造 Green。

判定：C2b 保持 pending。下一波 BG-00ay 转可独立的首链配置/安装恢复代码：优先审当前 approved 但 binding0 的产品错误原因与恢复入口是否缺一个确定性只读诊断，先方案/RED/最小实现；不启 Host 或强行写配置。正式原链来源齐备后再回 C2b 同库联合证明。
