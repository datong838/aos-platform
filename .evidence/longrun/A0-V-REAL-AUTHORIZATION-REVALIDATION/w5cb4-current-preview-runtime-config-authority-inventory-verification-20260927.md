# W5CB4 当前预览实例 Runtime 配置权威只读盘点（2026-09-27）

## 当前读回

- `m1@a8e679f7`；当前预览 preflight `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，库 `aos_current_preview_20260927@a0v_106`、四包 published、唯一安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` approved、Runtime binding=0。8080/8434 本机可达、18181 无监听。
- 使用 `inspect_runtime_configuration_authority` 对**当前新库**只读复核：八项 counts 全部为 0，blockers 恰为八项，`ready=false`。未写配置、未 Apply/启用、未触发商城源/Provider/旧 Run。测试库的后到授权只适用于自动化隔离测试，不扩大到业务数据清理。

## 正式 Owner 与产品入口差距

| 准入项 | 正式后端写入口 | 当前前端可操作性 | 下一切片处理 |
| --- | --- | --- | --- |
| frozen responsibility plan | `/v1/aip/production-contracts/responsibility-plans` create/revise/freeze | `ProductionContractsPage` 已调用公共 client | 安装页导航至现有正式入口，并标明与当前安装尚未绑定 |
| active runtime policy | `/v1/aip/model-runtime/policies` | `ModelRuntimePage` 当前是权威状态读页，未发现直接 POST 调用 | 只读阻断与导航，后续补正式版本化编辑 |
| active data classification | `/v1/aip/runtime-guard-policies/data-classifications` | 未发现前端调用 | 后续正式配置表单，不用默认值 |
| active egress | `/v1/aip/runtime-guard-policies/egress` | 未发现前端调用 | 同上 |
| active network | `/v1/aip/runtime-guard-policies/networks` | 未发现前端调用 | 同上 |
| active quota | `/v1/aip/model-governance-policies/quotas` | `CapacityPage` 有版本化配额提交/回读 | 安装页导航至现有入口，仍需 exact 生效读回 |
| active budget policy | `/v1/aip/model-governance-policies/budgets` | 未发现前端调用 | 后续正式预算策略表单 |
| active budget revision | `/v1/aip/budgets` | 未发现前端调用 | 后续正式预算表单及币种/单位/上限审查 |

以上路由存在不等于配置已建立；UI 表单存在也不等于 current authority。无当前权限、金额和审批的默认填充。

## 下一切片的文件级边界

- 后端：新增只读当前安装配置阻断摘要，复用 `scripts/a0v_canonical_ecommerce_first_install.py` 所列八项 SQL 的正式逻辑，避免产品页本地猜测；限定 `org-org/dev-project` 当前安装，禁止启动 Runtime。
- 前端：`apps/web/src/pages/s2/assetBundles/RuntimeInstallationPanel.tsx` 显示八项中文阻断、现有两项正式页面导航，其余明确“配置入口待建”，不把“准备运行资源”按钮当绕过配置入口。
- 测试：后端租户/安装/无配置/部分配置只读反证；前端八项缺口与禁入状态；专项、累计回归、浏览器读回后另落 verification 再提交。

本文件只证明权威盘点，**不**声称配置波或 BG-00 完成。P2g30b 当前 RETURN Action 的 RED `REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED` 仍待正向 producer，保持独立主线。
