# AIP-P9 Content-1 草稿控制链实施清单

> 状态：`v1.3 / C1-0～C1-1A CODE_GREEN / C1-1B BLOCKED_EXTERNAL`
> 日期：2026-08-16
> 基线：`m1 / w1-aip @ 2ff5a60`；共享记忆 `AOS-000066`
> 唯一真实租户：`org-org/dev-project`；`dev-org/dev-project` 仅负向 canary

## 1. 目标与裁决

Content-1 只交付内容策略、脚本、标题和平台版本的 **Draft 控制链**。它不发布内容、不创建 MediaJob/AvatarSession、不操作平台、不把本地模板或调用方文本伪装成模型产物。

当前 `runnable=0`，Provider/Model/Route/Policy/Eval/Health/Capacity/Price 和 Binding 均为空。因此本轮允许完成 authority、readiness、幂等、unknown/reconcile、审核与测试；真实文案生成保持 `BLOCKED_EXTERNAL`。

## 2. Authority 复用

| 语义 | 唯一 owner | Content-1 用法 |
|---|---|---|
| Brief | `TaskBriefRevision` | exact 输入，必须绑定真实 Product/Evidence |
| 编排 | `StageTemplateRevision + ResponsibilityPlanRevision` | 只读 exact 组合，不复制模板 |
| 执行 | `TaskRun + AgentRun` | 只有 exact running AgentRun 才能调用模型 |
| 模型 | AIP-7 `ModelRoute/Policy/Provider/Eval/Capacity/Price` | 由 resolver 重读，调用方 readiness 无效 |
| 草稿 | `aip_artifact` | `artifact_type=content_draft`；只保存内容引用/hash/marking/evidence，不建第二 Draft Store |
| 审核 | `EvalReportRevision + ReviewIssue` | 复用 W2-C authority，不复制审核表 |
| 用量 | `UsageReceipt + LineageEvent` | Provider 成功必须同包可追溯 |

## 3. 分波与精确边界

### C1-0 · strict contract 与只读 readiness

新增/修改候选：

```text
services/aos-api/aos_api/aip_content_contracts.py
services/aos-api/aos_api/aip_content_draft_readiness.py
services/aos-api/aos_api/routers/aip_content_drafts.py
services/aos-api/tests/aip/test_aip9_content_draft_readiness.py
services/aos-api/tests/aip/test_aip9_content_draft_api.py
services/aos-api/aos_api/routers/domain_manifest.json
services/aos-api/aos_api/routers/domain_aggregates.py
```

只新增 `POST /v1/aip/content/drafts/readiness`。请求只能携带 exact Brief/Pipeline/TaskRun/AgentRun 与 variant/channel；服务端逐项回读 tenant、状态、revision/hash、Route/Policy/Binding 和运行门。响应为 `ready|blocked|unknown`、稳定 blocker、dependency snapshot hash；本波不调用 Provider、不写 Artifact、不新增迁移。

实施记录（2026-08-16）：C1-0 已由 `w1-aip@4392046` 实现并于 `m1@8d96fcd` 串行集成。w1-aip 与 m1 均完成 Content/Manifest 累计 37 项测试，525 项路由聚合一致。当前没有 canonical `BudgetRevision` authority 可供 exact re-read，因此即使调用方携带预算引用，服务端仍稳定返回 `CONTENT_DRAFT_BUDGET_AUTHORITY_UNAVAILABLE`，不得把“有引用”解释为预算就绪。该结果为 `CODE_GREEN / OPERATIONAL_BLOCKED`，不构成真实 Provider、模型输出或 runnable Agent 证据。

### C1-1 · Artifact writer 与幂等 Receipt

先复审 `aip_artifact` 的内容对象存储适配器。只有在内容先写入受治理对象存储并返回 `contentRef + contentHash + schemaRef + marking + evidenceRefs` 后，才允许同事务登记 `aip_artifact`。调用方不得提交 inline provider answer 作为 authority。

幂等键必须覆盖 Brief/Pipeline/AgentRun/variant/channel/prompt hash；同键异 payload 冲突。Provider 结果未知时不得创建第二次生成，进入 unknown/reconcile。若现有 Receipt 无法表达，才允许 additive migration；不得新建第二套 ContentDraft 表。

2026-08-16 复审裁决：`aip_artifact` 与 `aip_production_contract_receipt` 可直接复用，现有 `AipTaskStore.record_artifact()` 因随机 ID、缺少幂等回放、受治理对象复验和 unknown 语义，不得直接暴露为 Content Draft writer。C1-1 拆为：

- **C1-1A（可编码）**：增加 strict registration contract、默认失败关闭的 Content Object verifier、同事务 `aip_artifact + aip_production_contract_receipt` 写入边界及 replay/drift 测试。默认 verifier 不可用时必须稳定 blocked，不能写任何行。
- **C1-1B（后置）**：接入真实受治理对象存储 verifier 与 canonical BudgetRevision owner；只有 exact re-read GREEN 后才允许第一条真实 Draft。

2026-08-16 二次代码与方案对账确认：

- 现有 `aip_artifact` 是 Artifact 元数据和谱系权威，不是 Blob/对象正文存储；`AipContentDraftStore` 默认使用 `UnavailableContentObjectVerifier`，这是正确的失败关闭边界，不得改成“只校验请求自报 hash”。
- 现有 `BudgetPolicyRevision` 只表达模型运行预算政策引用，不能代替 Content Pipeline 要求的 exact `BudgetRevision`；当前代码库和已冻结方案中均无可复用的 canonical `BudgetRevision` owner。
- 因此 C1-1B 不是遗漏一个本地 adapter，而是真实对象存储与预算治理两项外部基础设施门。未出现 owner、exact read API、真实租户记录与负向 canary 证据前，不新建本地第二真源，不启动 C1-2/C1-3。

C1-1A 精确候选范围：

```text
services/aos-api/aos_api/aip_content_contracts.py
services/aos-api/aos_api/aip_content_draft_store.py
services/aos-api/aos_api/routers/aip_content_drafts.py
services/aos-api/tests/aip/test_aip9_content_draft_store.py
services/aos-api/tests/aip/test_aip9_content_draft_api.py
```

不新增 migration、不修改页面、不调用 Provider、不写真实数据库。验证仅使用事务 fake connection；测试 positive 仅证明控制面状态机，不作为 operational evidence。

C1-1A 实施记录：已由 `w1-aip@fc09c84` 实现并于 `m1@2ff5a60` 串行集成；累计 42 项 Content/Manifest 测试 GREEN，运行时路由 4254、OpenAPI 路径 2476。默认 object verifier 不可用时在进入数据库前失败；受控测试正向路径只写 `aip_artifact + aip_production_contract_receipt`，同键异 payload 冲突。该结果不代表 C1-1B、Provider 或 runnable Agent operational GREEN。

### C1-2 · exact LLM 执行

复用 `AipAgentRunService + LLMAdapter.chat_exact()`。只有 AgentRun running、resolver READY、capacity reservation、Provider invoker、Usage Receipt 和 artifact writer 全部可用才生成 Draft。默认 invoker 继续 `provider_invoker_authority_unavailable`；禁止 Northampton/sample/local answer/mock fallback。

### C1-3 · Eval/Review 投影

将 exact EvalReport 和 ReviewIssue 投影到 `ContentDraftProjection`。高风险功效、过期价格/库存、无 Evidence claim 必须形成 Issue 并阻断“可交付”；修订生成新 Artifact，不覆盖旧 Artifact。

## 4. 失败语义

| 缺口 | 稳定结果 |
|---|---|
| Brief/Pipeline/Run 不存在或跨租户 | `404` 或 `CONTENT_DRAFT_DEPENDENCY_NOT_FOUND` |
| exact ref 漂移 | `CONTENT_DRAFT_DEPENDENCY_DRIFTED` |
| AgentRun 非 running / Binding 不 ready | `CONTENT_DRAFT_AGENT_NOT_RUNNABLE` |
| Provider/Route/Eval/Capacity/Price 未就绪 | 原始 canonical blocker 归一后返回 `blocked` |
| Provider 断流且无法确认结果 | `unknown`，只允许 reconcile |
| Artifact/Usage/Lineage 任一写入失败 | 不得返回 Draft success |

## 5. 验收与外部门

- Contract/API：strict extra-forbid、Principal tenant、双租户、exact drift、稳定 blocker。
- Readiness：真实 `org-org/dev-project` 当前必须诚实返回 blocked；canary 不可见。
- Positive 状态机只允许测试注入的 canonical fake services，不作为 operational evidence。
- 累计 AIP-9、OpenAPI、manifest、Web SDK 和全量邻接测试 GREEN。
- 页面变更后必须内置浏览器验证；C1-0 无页面，browser=N/A。
- 第一条真实 Draft 必须同时给出 Provider、Usage、Artifact、Lineage、Eval/Review Receipt；在外部门未满足前不得宣告 Content-1 operational GREEN。

## 6. 评审结论

本清单不改变既有架构，修正了“直接把 LLM 字符串写入 metadata”和“重试重复调用 Provider”的风险。实施顺序固定为 C1-0 → C1-1A → C1-1B → C1-2 → C1-3；C1-0、C1-1A 已封板，C1-1B 等待真实对象存储与 BudgetRevision owner。结论：`C1_0_C1_1A_CODE_GREEN / C1_1B_OPERATIONAL_BLOCKED`。
