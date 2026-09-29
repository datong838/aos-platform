# W5CB4 BG-00at｜E03/BG-00 最小合法配置来源/绑定盘点

方案：`w5cb4-bg00at-e03-config-binding-inventory-plan-20260929.md`。无代码或当前库写入，不读取商城源。

## 当前事实

- `scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 退出0：`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、当前 `aos_current_preview_20260927@a0v_114`、approved 安装1、published 4、runtime binding0。`scripts/a0v_current_runtime_host_preflight.py --signed-receipt ...` 退出2：`SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED`。
- 当前库 READ ONLY SQL：org-org/dev-project 的 `bundle_installation=1`；`extension_runtime_operation/binding/configuration/configuration_stage_request/host_assignment` 均0；enabled Host identity0；`aip_budget_activation_preview/decision/receipt` 均0。`read_candidates(TenantScope('org-org','dev-project'))` 的 responsibility_plans/runtime_policies/data_policies/egress_policies/network_policies/quota_policies/budget_policies/budgets 八项逐项0。查询退出0，无 dev-org 写入。
- `runtime_configuration_candidates.py` 只读统计，不能给安装绑定。现有 `/bundle-installations/{id}/configuration-sources` 仅展示当前 frozen 职责计划和 active 运行策略；`ConfigurationStageRequest` 只收其 exact refs，`assemble_current_configuration` 从运行策略推导并复验其他六类及预算，不让用户在 Stage 里随意拼八项。当前 binding0 导致登记目标不可用，且配置 Stage 凭据未配置；本波没有尝试绕过。

## 产品入口缺口与下一最小点

- `RuntimeInstallationPanel.tsx` 的八候选引导已存在；其中 network_policies 和 budget_policies 明确 `href:null`，当前显示“产品配置入口待建”。责任计划、运行策略、数据/出站、配额/预算修订已有入口或草稿入口；API/Store 生产者存在不等于当前已授权源。预算 draft 可建，active API 仍 422 `AIP_BUDGET_ACTIVE_APPROVAL_REQUIRED`，正式外部费用上界、不同 checker 和同事务消费缺失。
- 下一波 BG-00au 先读网络/预算策略的产品方案、API 契约和现有页面，限定为“从安装缺候选指向合法草稿准备/只读核对入口”，避免伪造 active；先写前端失败用例再最小接线。如无合法可用表单，则只交付可审计的缺口说明/只读链接而不造虚假提交按钮。真实绑定需当前八源、独立凭据/Host Owner 与审批，继续后置。

API `/v1/health`、`/v1/ready` 和 Web `/aip/skill-publish` HTTP200，18181关闭（BG-00aq 当前读回）；页面 200 不代表业务首链。browser-pilot 不可用，未做新的交互截图。Host/worker/Provider 保持关闭。
