# BI-W10 Case 精确选择预检验收

- 任务：`BI-W10-CUTOVER-EXACT-SELECTION-PREFLIGHT`
- 租户：`org-org/dev-project`
- 范围：只读精确选择、Case 写前 resolver、HTTP/OpenAPI 合同；未创建真实 Case/Run。

## 实现结果

1. 新增 principal-scoped `GET /v1/ecommerce/investigations/case-selection`；当前租户的 Channel、BusinessEntity 与 Binding 引用由唯一 active Shop canonical head 确定性派生。
2. `POST /cases` 在持久化前重新读取同一选择并逐个比较五类 exact ref；SourceReadiness 非严格 READY、Profile/Scope authority 缺失或任一 revision/hash 漂移时均不进入 Case store。
3. 当前真实回读识别到 Shop `BusinessEntityRevision/niushop:1:1`，但 SourceReadiness 仍为 `10 ready / 2 failed`，且生产 InvestigationProfile/Scope authority 尚未安装；因此 `caseCreatable=false`、`runCreatable=false`，没有制造占位 ref。
4. 新路由已纳入确定性 OpenAPI 与 route inventory，operationId 为 `ecommerceInvestigationCaseSelectionGet`；既有重复路由基线未变化。

## 验证结果

- 选择 resolver 与 HTTP 专项：`18/18` GREEN。
- Case/Run/Lifecycle/Migration/Schedule/SourceReadiness 累计：`58/58` GREEN。
- OpenAPI 合同与双干净进程导出：`16/16` GREEN。
- `compileall`、`git diff --check`：GREEN。
- 浏览器验收：`N/A`，本切片无页面改动；真实 Case 与经营参谋页面联动时必须重新验收。

## 安全结论

- `NO_MANUAL_PIPELINE / NO_DLQ_REPLAY / NO_REAL_CASE_CREATE / NO_REAL_BUSINESS_MUTATION / NO_PROVIDER_EXECUTION / NO_MIGRATION / NO_EXTERNAL_EFFECT / NO_RELEASE`。
- P07/P08 继续由独立只读监测等待下一自然窗口，本切片不改变其历史或当前状态。
