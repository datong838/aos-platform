# W5CB4 BG-00av｜网络/预算策略正式提交权威只读审计

## Rules 与上位方案

按 231-3/5/9、BG-00at/au、网络/预算策略合同、Store/API、现有 E17 预算审批证据，查当前合法提交前置与 Owner。只读查询当前库，不写配置、不填假 approvalRef、不启 Host/worker/Provider；无合法 authority 的当前实例保持阻断，继续可独立首链研发。

## 文件级核查

1. 读 `aip_network_policy_contracts.py`、`aip_network_policy_store.py`、`routers/aip_runtime_guard_policies.py` 与 `aip_model_governance_policy_contracts.py`、Store/router，区分 draft 条件、active 条件及真正审批验证。
2. 当前库只读复核正租户 Egress/Network/BudgetRevision/BudgetPolicy 有效行、预算预览/决定/Receipt、OIDC checker 可用性；不取商城源或凭据。
3. 对照产品入口与 231 的合法审批，列出下一独立代码波或返回 C2b/BG-00 配置主线；不把字符串 approvalRef 当决定。
