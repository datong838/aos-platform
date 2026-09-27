# W5CB4 D01 C2b0：联合正向前置合同审计结果（2026-09-27）

## 结论

**C2b 完整同库联合正向未通过，未做当前库写入。** 四个相关专项独立复核 `4 passed, 7 warnings`，分别证明正式原链建档、原 Origin 可读、Schema 样式两阶段选择/撤销，以及 Atomic 在 fake Owner 下的控制流；它们不是同一个 PG 事务的 AgentRun Owner Receipt，不能相加成 C2b 通过。

## 精确缺口

1. 正式 `test_product_event_analysis_bootstrap_pg.py::formal_case` 自己的独立回读明确产生一条 `aip_task_run.status='paused'`。`NaturalD01Issuer` 要求原 TaskRun `running`、Task `executing`、三阶段已批准且内容 hash 未漂移；不能直接拿已暂停 fixture 冒充可发行正例，须走正式 Task/Plan 审批和恢复 Owner。
2. 当前两阶段选择 PG 测试建立的是单阶段最小 Plan 与独立 checker，尚无原 `AnalysisContinuationOrigin` 的同一 Context/Receipt 与完整来源集合。不能改已批准 Plan，把运行后的 Method/Query/Bundle 追填进去；C2a 已清除此错误假设。
3. `AipAgentRunService._create_in_transaction` 的真实 Owner 在写前要求 active AgentInstance、active 同实例 SkillBinding、exact published Skill/Logic 和健康 Capability。当前业务实例最近独立证据仍为六个 `provisioning`、binding 0；没有这些权威时，代码不应写 AgentRun。为了一个测试合成 active 绑定/逻辑/模型路线，会掩盖 BG-00 首链真实准入缺口。

## 后续路由

- C2b 保留在 `w5cb4-d01-c2-full-owner-joint-proof-plan-20260927.md`，未 GREEN；待 BG-00 最小合法绑定与正式 Task 恢复路径具备后，再在隔离 PG 执行原链→批准包→来源/Grant→唯一 Owner Receipt、撤销/漂移/未知提交负向。不得用 mock、直接 SQL 改状态或当前库夹具填补缺口。
- 下一施工波转 BG-00 首链最小正式 Skill/Logic/ModelRoute/RuntimePolicy/Capability/ResponsibilityPlan 依赖闭合；优先做合法 Owner/入口和可独立验证的最小切片，不补 37 Skill 全量。
- 8080/8434 仍为最新 m1 `cad0b905` 后的安全预览，a0v_106、18181 不在，Host/worker/Provider 未启；本审计不读商城源、不删卷、不迁库、不回放旧 12 Run。
