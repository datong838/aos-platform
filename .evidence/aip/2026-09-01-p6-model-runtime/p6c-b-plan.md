# P6C-B · 用量归因与版本化限额施工方案

> 执行状态：`CODE_TEST_BROWSER_GREEN`。真实租户仅做权威只读验收；版本创建、精确回读与 CAS 冲突在 `dev-org/dev-project` 隔离 canary 完成，运行绑定未自动切换。

## 上位目标与事实基线

- 对应清单 `AIP-P6-106`、`AIP-P6-107`；继续复用 P6C-A 的 Usage Receipt、CapacityPool、QuotaPolicyRevision、BudgetRevision 与 BudgetPolicyRevision，不建立第二套用量或限额权威。
- `org-org/dev-project` 当前有 16 条实测 Usage Receipt，全部带 canonical lineage，且 8 个 lineage 均以真实 TaskRun 为根；当前没有显式 UsageAttribution。页面必须能解释租户与任务用量，同时把 Agent、Logic、模型缺少归因凭证明确呈现，禁止显示伪造的 0。
- 当前 canonical quota head 为 `quota-qyh-text-dev@1`、head version 1；旧版本已有并发、单次输入/输出 Token 与小时/日请求上限，但没有 RPM/TPM 字段。兼容回读必须保留“未登记”，新 revision 才允许登记 RPM/TPM。

## 单一权威设计

1. **归因读取**
   - Usage Receipt 仍是数量唯一真源；调整只消费 append-only UsageAdjustment。
   - 租户维度直接由 tenant scope 聚合；任务维度只从 Usage Receipt 的 lineage → canonical TaskRun/PlanRevision 解析。
   - Agent、Logic、模型维度只消费显式 UsageAttribution；当前不存在时返回 `missingReceiptCount`，不从 provider 名称、页面状态或任务标题猜测。
   - 扩展既有 AttributionSubjectType 支持 `logic`，供后续运行生产者写 exact attribution；不回填、不重放历史 Provider 调用。

2. **版本化限额**
   - 在既有 QuotaPolicyRevision 增加成对可空的 `rpmLimit`、`tpmLimit`，旧 revision 可精确回读为“未登记”；新 revision 由现有 POST + `If-Match` CAS + Idempotency-Key 发布。
   - cost overview 返回运行绑定的 quota ref、当前 head exact ref/head version、RPM/TPM、并发、Token、小时/日请求上限；若 head 已前进但运行绑定仍指向旧 revision，页面明确显示差异，不把保存新版本冒充运行生效。
   - 预算继续读取 exact BudgetPolicyRevision → BudgetRevision，显示 revision/hash、日/月上限、硬停与未知用量策略；本子包不原地修改预算，也不绕过两段 authority。

3. **页面产品合同**
   - “用量仪表盘”在日/近 7 天/近 30 天切换时同步展示租户、任务、Agent、Logic、模型五类归因；有凭证显示 Receipt 与 Token，缺凭证显示“暂无归因凭证”。
   - “速率限制”展示 canonical quota head 与 exact 运行绑定，提供下一版本编辑入口；保存只创建新 quota revision，服务端冲突原样提示，成功后精确重读并显示“新版本已保存、运行绑定未自动切换”。
   - 页面不再依赖 legacy `capacity_limits` 默认 60/60000 作为权威配置；兼容接口仅保留非权威说明，不参与版本化裁决。

## 测试与验收

- API：租户隔离、task lineage 聚合、无显式归因的缺证语义、logic attribution、周期过滤、quota 旧版本兼容、新版本 RPM/TPM、CAS 冲突和精确重读。
- Web：严格 parser、五维归因纯逻辑、缺证不归零、quota revision draft/响应匹配、页面交互与错误恢复。
- 浏览器：在 `org-org/dev-project` 读取 16 条 Receipt 的租户/任务归因，核对 Agent/Logic/模型缺证；隔离 canary 通过同一 API 合同验证版本创建/冲突/精确重读，不调用 Provider、不切生产流量。
- 累计：P6A～P6C 专项、TypeScript、production build、diff-check；随后形成 Delivery Receipt、authority CAS、memory sync/validate/gate 与 Prime 回读。

## 硬边界

- 不解析明文 Secret，不调用 Provider，不回放历史流水线，不改真实经营数据，不自动切换 route/policy binding，不迁移或发布。
