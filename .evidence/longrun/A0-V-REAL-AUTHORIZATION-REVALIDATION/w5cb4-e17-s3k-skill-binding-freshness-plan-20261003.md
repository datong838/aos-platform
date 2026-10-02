# E17-s3k 职责冻结时 SkillBinding 当前就绪门：文件级方案

基线 `m1@c0967688`、Authority `AOS-001181`；真库 a0v_135 只读。上位 231、E17 签名 BI Plan 冻结清单和 s3j 审计要求原 Plan 必须从 assignee 的可用且新鲜 Binding 取得覆盖，不得手插 active 行做正向。此波只修冻结读取门，不创造正式 Skill/Model Eval 身份或打开 Host。

## 问题与目标

`aip_production_contract_store.py:_responsibility_blockers` 对 agent-instance 仅取 `status='active'` 的 SkillBinding 和它指向的 CapabilityBinding；CapabilityBinding 复核 active/health/operational/fresh，但 SkillBinding 本身的 `readiness`、`dependency_snapshot_hash`、`readiness_expires_at` 未读。`bind1_001_operational_bindings.py` 为其提供列，原 `AipSkillBindingReadinessService.evaluate` 才能产生 available 与 snapshot。目标是在原 Plan create/revise/freeze 使用的同一个读取函数内拒绝未评测或过期的 active SkillBinding。

## RED 与最小实现

1. 在 `services/aos-api/tests/test_w2b_production_contract_store.py` 的自动 disposable PG 创建 `org-org/dev-project` 的合法测试父行、AgentInstance、CapabilityBinding。直接插入 active SkillBinding **只作负例攻击输入**，分别让它的 readiness 为默认 unknown 与 `available` 但过期。断言 Plan readiness blocked、对应 slot uncovered、freeze 不产生 Receipt/不推进 head。旧逻辑若误报 ready 应出现 RED；绝不将手插行计作发布/绑定正向。
2. 在 `services/aos-api/aos_api/aip_production_contract_store.py` 最小扩大原 SkillBinding SELECT 至 `readiness,dependency_snapshot_hash,readiness_expires_at`；只有同 assignee 的 active 且 available、snapshot 非空、expiry 晚于当前事务检查时间的 Binding 可贡献 capability refs。缺失时用可区分的 `SKILL_BINDING_NOT_READY` / `SKILL_BINDING_STALE` blocker；完全无 active 仍保留原 `SKILL_BINDING_NOT_ACTIVE`。不修改原绑定 Store、Capability 语义、正向实例数据或旧状态。
3. 专项新两例与既有 `test_w2b_production_contract_store.py`、Binding readiness 相邻回归；若已有测试故意直插未评测 active 行并期待正向，按原授权语义修正其夹具，仅在 disposable PG 中构造来源，不放宽生产门。静态/租户/Receipt 回读。签名 Growth 测试有 OCI/Receipt 环境门，不满足时只能报 skipped，不冒充通过。

## 边界与残余风险

该修复证明“active 状态不足以通过 Plan readiness”，但单靠读列仍不能防止拥有直接写表权限的角色伪造 `available` 与 snapshot。数据库级发布/就绪签发来源与当前实例六个真 Binding 需独立下一波；不能把本波标为 frozen Plan 正向。当前真实库、Host/worker/Provider均不写不启，未知外部结果不重发。
