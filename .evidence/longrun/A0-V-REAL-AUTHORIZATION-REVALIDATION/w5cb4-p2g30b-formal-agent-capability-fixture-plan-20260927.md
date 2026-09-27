# W5CB4 P2g30b 正式 Agent／职责／Capability 隔离来源波（2026-09-27，编码前）

## 目的与上位约束

- 承接 `w5cb4-p2g30b-return-action-source-audit-verification-20260927.md`。当前 RETURN Action 正向集成测试原内容命令的三个引用来自合成 helper，未有当前 AgentInstance/ResponsibilityPlan/Capability Owner 行；不能因此削弱生产 `_agent_capability_authority` 或跳过 maker/checker。
- 本波只修**测试权威来源**，不改生产门：隔离库使用公共 AgentRegistry/CapabilityRegistry/ProductionContract Stores 建立 published/active/frozen/available 当前记录，重算命令 exact refs 与 request hash，再执行原内容、RETURN 和 Action RED。模板必须由测试自有的已发布来源或正式发布接口提供；不能借旧业务租户数据。

## 文件级与验收

1. 先读公共 Registry/Plan 合同与现有测试 helper；只改 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py` 的 `formal_brief_sources=True` 路径，必要时新增该目录的窄测试辅助模块。其他受控旧用例保持原行为。
2. 隔离库经公共 Owner 写入：AgentTemplate/AgentInstance、CapabilityRevision(available)、有 `content.generate` 且指定该 Agent/Capability 的冻结 ResponsibilityPlan。每项再次用独立连接读回 exact revision/hash、当前 head 与状态；生成原命令的对应 refs 后重新计算 command request hash。若已有已发布模板不匹配，使用正式 publish，而不直接 SQL 造通过行。
3. RED 正向探针必须越过 `AgentInstance authority is missing`，直到下一项真实缺口；负向覆盖旧 revision/非 available Capability/Plan 不是 current。不得 monkeypatch 正式 Owner guard、不得用旧批准作新批准。
4. 专项/相邻累计、无 Provider/商城源/当前实例写入、verification→m1 提交；随后返回 producer。自动化隔离测试库可按用户后到授权由夹具清理，业务库和卷不删。

若正式模板/Capability 无法在隔离环境建成，本波记录具体门，生产路径继续 fail closed；转做现有六个产品配置入口，不耗费主线时间硬造通过。

## 只读复核后细化的停止边界

- `AipProductionContractStore._responsibility_blockers` 要求 Agent 所属 active SkillBinding 挂上 active/healthy、operational available、dependency snapshot 未过期的 CapabilityBinding；目录 Capability `published/available` 本身不足以让职责计划 `ready/complete`。本切片不是简单改三个 ref；需另一个正式能力绑定与健康观察子波。
- 因此当前不以 SQL 伪造 Binding/健康或 monkeypatch Owner 来让 Action 绿。先把此要求固定为后续能力接线任务，当前开发主线切换到新实例真实配置入口；RETURN Action 继续明确禁入。
