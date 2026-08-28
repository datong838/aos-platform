# BI-W10-02 L1 InvestigationProfile/Scope Authority Acceptance

- Task: `BI-W10-02-PROFILE-SCOPE-AUTHORITY`
- Tenant: `org-org/dev-project`
- Negative isolation canary: `dev-org/dev-project`
- Base authority: `AOS-000387`
- Browser: `N/A`（本切片不改页面；真实 Case/Run 页面联动另行验收）
- Safety: `NO_DB_WRITE / NO_REAL_CASE / NO_REAL_RUN / NO_MANUAL_PIPELINE / NO_DLQ_REPLAY / NO_PROVIDER / NO_EXTERNAL_EFFECT / NO_MIGRATION / NO_RELEASE`

## 方案与代码一致性

1. 电商 L1 目录发布稳定、版本化且与租户无关的 Profile/Scope；AIP 运行组合继续由后续 resolver 解析。
2. Profile 阶段严格为 `portrait → diagnosis → solution-design`，能力身份来自 163 的通用原子 Skill，不复制大 Skill 或角色私有逻辑。
3. Scope 严格为 `current-business-entity / full-store / read-only`；具体 Shop 仍由 principal-scoped Case selection 注入。
4. `caseCreatable` 与 `runCreatable` 独立裁决；`runBlockers` 不再污染 L1 Case authority，也不会被误解为运行授权。

## Exact authority

- Profile: `InvestigationProfileRevision/ecommerce.initial-store-analysis@1`
- Profile hash: `sha256:267e3ec1a06662793ef1c71a7a70cc4952fbe3833e910caa63bc8e5399ae96fb`
- Scope: `InvestigationScopeRevision/ecommerce.current-business-entity.full-store.readonly@1`
- Scope hash: `sha256:a8f298b03dcdd413df828b71abe9a2bb2c46ad17972162eb6d6100278fed20ce`
- Required facts: `Shop, Product, ProductSku, Category, Order, OrderLine, Shipment, CustomerLite, Weapp, SystemConfig, ProductReview, Payment`

## Real read-only probes

At `2026-08-28T09:47:45Z`, `org-org/dev-project` resolved the canonical Shop and both L1 refs. SourceReadiness remained `failed`, therefore:

- `caseCreatable=false`
- `runCreatable=false`
- `blockers=[SOURCE_READINESS_NOT_READY]`
- `runBlockers=[AIP_PRODUCTION_COMPOSITION_NOT_RESOLVED, CASE_SELECTION_NOT_CREATABLE]`

At `2026-08-28T09:49:27Z`, the negative canary resolved no Shop, remained `sourceStatus=blocked`, and returned `CANONICAL_SHOP_SELECTION_UNAVAILABLE`; it did not borrow the real tenant's BusinessEntity.

The independent natural-run monitor remained `10 ready / 2 failed`, with P07 and P08 failed through `2026-08-28T17:53:25+08:00`. This slice did not reinterpret or mutate those facts.

## Verification

- Profile catalog + Case selection: `10 passed`
- API/OpenAPI + catalog/selection: `39 passed`
- Full Business Investigation + SourceReadiness + OpenAPI cumulative suite: `401 passed`
- Python compileall: GREEN
- OpenAPI deterministic export: GREEN; existing path/operation inventory unchanged, response schema adds only `runBlockers`
- `git diff --check`: GREEN

## Residual gates

- L1 Profile/Scope authority is closed.
- SourceReadiness is not closed until P07/P08 produce valid next-natural-run evidence at the same cutoff.
- AIP production composition is not closed until exact Logic/StageTemplate/SkillBindingSet/ResponsibilityPlan/ProductionContext can be resolved without drift or ambiguity.
- No runtime, pilot, external effect or release authorization is implied.
