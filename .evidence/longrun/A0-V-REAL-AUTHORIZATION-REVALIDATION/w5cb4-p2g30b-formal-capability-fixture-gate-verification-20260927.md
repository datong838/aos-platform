# W5CB4 P2g30b 正式能力来源门核验（2026-09-27）

- `test_ecommerce_content_review_pending_pg.py` 的 `formal_brief_sources=True` 只把 Brief 与四个源产物变成正式引用；原命令的 Agent/职责/Capability 仍由 `content_generate_command` 生成合成占位。负向 `test_ecommerce_content_repair_action_binding.py` 4/4 通过，生产 RETURN 提案保持 `REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED`。
- 只读复核公共 Owner：`ContentGenerateHostService._agent_capability_authority` 要求当前 AgentInstance、冻结且 `ready/complete` 的 ResponsibilityPlan、当前 `published/available` Capability。`AipProductionContractStore._responsibility_blockers` 进一步要求 Agent 所属 SkillBinding 指向健康、operational available、快照未过期的 CapabilityBinding。只建三行目录记录不足以成为可信的正向测试来源。
- 本切片没有写生产代码、没有放宽 guard、没有执行 Provider/商城源/旧 Run；当前新实例仍 `approved/not_prepared`、Runtime binding=0。下一次返回 P2g30b 前，须先完成公共能力绑定的正式隔离来源和有效期/健康测试；此测试建设与当前实例的配置入口开发串行交替，避免长时间停在测试夹具。
- 本 verification 是**门定位与安全停止**，不是 Action producer 通过；未提交的正向 RED 集成测试保留。不得推进 P2g30c 或声称返工自动续跑。
