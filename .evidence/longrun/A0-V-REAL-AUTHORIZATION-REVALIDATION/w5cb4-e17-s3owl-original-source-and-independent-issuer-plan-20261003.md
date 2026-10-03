# W5CB4 E17-s3o-w-l｜原 successor/Content 来源与独立发行接续方案

日期：2026-10-03。基线 `aos-platform/m1@4292eba2`、Authority `AOS-001220`。复习 231-1/5/9、W-L20、E17 s3o-w-k 及原 Store/Router/候选读者。真实库只读；仅 org-org/dev-project 正向，dev-org 零副作用；不启 Host/worker/Provider。

## 本波已核对的原生产门

1. `aip_responsibility_assignment_store.py` 原 successor 必须指向 exact frozen Plan。上一波签名隔离安装只生成 draft2，原调用返回 `SOURCE_PLAN_NOT_EXACT_FROZEN`，不能手工改 Plan lifecycle 或编造 ResolutionReceipt/Run 来凑正向。当前真实库的 Plan revision、AssigneeResolutionReceipt、TaskRun、AgentRun、Artifact 均为 0。
2. `aip_content_draft_readiness.py` 原 readiness 要求 exact Brief/StageTemplate/Plan/Eval/Capability、TaskRun/AgentRun 绑定、ModelRuntime、Budget；`_budget` 即使找到 active Budget 仍加 `CONTENT_DRAFT_BUDGET_BALANCE_AUTHORITY_UNAVAILABLE`，当前没有可被该服务判为 READY 的真实余额来源。`aip_content_draft_store.py` 默认 `UnavailableContentObjectVerifier` 明确拒绝；`routers/aip_content_drafts.py` 当前装配默认 Store。通用开发 ObjectStore 不构成 governed Content object authority。现有 FakeConnection/VerifiedContentObject 测试只证明单元逻辑。
3. `aip_assignee_resolution_store.py` 原 ToolBinding upsert 仅有版本冲突门；s3o-r 证明无同事务发行 Receipt。s3o-s 当前库 ACL 审计证明普通 runtime 同时能写 ToolBinding 和 RegistryReceipt，因此孤立加一个“存在 Receipt”读侧门可被伪造。其公共发行输入还缺正式 Tool/Agent/Capability、安装、批准与 actor 精确引用。

## 文件级执行顺序

1. 本波只读核对原生产门与当前记录，不修改当前库，也不把缺来源的 successor/Content 正向改成测试替身。将精确缺口同步到 D-waves 与 01/06；若当前权威尚缺正式来源，实例保持失败封闭。
2. 先关闭不依赖公共发行协议的 HTTP 身份漏洞：`services/aos-api/aos_api/routers/aip_assignee_authority.py` 对 ToolBinding upsert 和 Assignee resolution 两个写命令要求 `Principal.token_kind == "oidc"`、非空规范 subject，保留原角色门；tenant 继续只取已验证 Principal，两个请求本身没有 tenant 字段。拒绝必须发生在 Store 调用前。`services/aos-api/tests/aip/test_e17_s3owl_assignee_formal_actor.py` 用 spy Store 做开发 Principal/空白 subject/合法 OIDC 的入口 RED→GREEN；`tests/aip/test_e17_s3oq_tool_binding_issuance_pg.py` 的原 HTTP 版本冲突测试改用显式 test-only OIDC Principal，仅测试入口门和版本冲突，不宣称真实 OIDC 配置或 ToolBinding 正式发行。该改动不添加新来源字段、不改 DB、不使当前实例从禁入变放行。
3. 独立下一代码波先冻结 ToolBinding 正式来源、专用非 owner issuer、同事务 Receipt 和当前性消费合同；涉及 `services/aos-api/aos_api/aip_assignee_resolution_store.py`、发行连接/ACL migration 与 `tests/aip/test_e17_s3or_tool_binding_source_receipt_pg.py`。先在 disposable PG 上对原命令做受限身份 RED；仅当上位公共协议裁决和真实来源可验证时写最小生产代码。不得向当前库迁移或直接插 active 行。
4. 后续设计切片：为 BI `SET LOCAL ROLE aos_runtime` 与独立 Plan issuer 的冲突制定事务身份合同，复核 `asset_registry/tenant_transaction.py` 与原 SignedBIPlanPreparationService；不得给 issuer 加 runtime 成员资格作为捷径。

## 验收与风险

后续正向必须同时证明真实来源、租户隔离、原子 Receipt、幂等/CAS/回滚、当前版本、只读 Host 消费；签名隔离测试不等于当前正式身份。当前 Growth1.13 正式发布、八配置、六 Binding、Host Owner/assignment、自然首链仍待当前真实证据。文件级计划不算完成这些门。
