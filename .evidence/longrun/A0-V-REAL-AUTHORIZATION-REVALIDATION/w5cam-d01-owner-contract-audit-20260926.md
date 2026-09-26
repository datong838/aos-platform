# W5cam｜D01 正式 Owner 合同审计（第 1/6 步，非 verification）

本文件仅是 W5cam 第 1/6 步中间证据；本波未完成，不得作为 D01/首链成功。

1. 现有 `AipAgentRunService.create` 是正式 AgentRun Owner：在独立事务内按稳定 key 锁定、先读 registry Receipt，核 Task/TaskRun/Plan exact 版本、当前 AgentInstance、active SkillBinding、Skill 对 Logic 的已发布 exact 绑定与健康 Capability，然后写 queued AgentRun 和 Receipt。`transition(...running)` 另经模型/Provider/价格/健康与 capacity reservation。旧脚本的固定 ID/空 `inputRefs` 不可复用。
2. 泛型 `create` **不核** Task/TaskRun 当前运行状态或 Plan approval；D01 Worker 才严格核 running TaskRun、executing Task、approved Plan、三阶段顺序和 D01 assignee。因此 pack-owned issuer 必须在签发前核这些状态，不能只拼泛型请求。取消/撤权竞态必须由 exact 版本/状态再检及 Worker 二次门挡住；queued 不等于模型已调用。
3. `PostgresAipProductionCompositionSource.read` 是只读来源，可核 D01/D02/D03 已发布 Logic、Skill/Binding、frozen stage/responsibility、production context 和 readiness，但不产出 D01 方法/指标/Query/EvidenceBundle/授权预算包。绑定含 `model_route_ref`、`runtime_policy_ref`、`budget_policy_ref`，不能猜默认 route。
4. D01 `PortraitGenerationCommand` 需要 current MethodRevision、EvalContract、至少一条 MetricDefinition→同 cutoff QueryResult→EvidenceBundle+DisclosureGrant、BudgetRef、CapacityReservationRef、数据分级和稳定 attempt。`read_portrait_inputs` 要求 AgentRun 的 `inputRefs` 已声明完整 exact inventory；目前没有可见的自然装配者。MethodRevision 的算法是描述性 `descriptive_snapshot_v1`，不可以从 9/17 历史商品 Receipt 虚构 9/26 新鲜事实。真实 PG 当前 MethodRevision/运行 TaskRun 为零。

下一步文件级 RED 应首先证明一个隔离 PG 正例可从**治理后的完整来源包**选择 D01 packet，而不读商城源、不伪造查询结果；并用现有 AIP Owner 稳定 ID/Receipt 建唯一 queued AgentRun。无合法 packet 时只返回可解释 blocker。随后才由 Host 消费 W5cal 候选；不能先把 Host 接到收费 Provider。原 12 Run 退休是后置维护，不作为本波业务验收。
