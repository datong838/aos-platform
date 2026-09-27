# W5CB4 当前出站策略产品入口波（2026-09-27，编码前）

## 上位与现状

- 231 BG-00 / 231-5 要求安装后的能力调用仍受出站、费用、审批、幂等边界约束；页面配置不是调用许可。当前新库出站策略 active 候选为 0，运行实例未绑定。上一波数据分类草稿也未激活。
- 正式 Owner `/v1/aip/runtime-guard-policies/egress`。合同只允许 HTTPS/443、Agnes 主机白名单、无公网 fallback、未知目的地 block；新主机以前向 `api.agnes-ai.cn` 为准，历史 `apihub` 主机不在本次新建入口中提供。active 必须确认 region；本波 draft 的 regionState 固定 unknown、region=null，不代填部署地域。

## 文件级清单

1. `apps/web/src/pages/s2/RuntimeEgressPolicyPanel.tsx`：用户填 policy ID、owner、approvalRef、有效窗并主动选择唯一当前 Agnes host；只建 draft，无 active/Provider 调用；现有 ID 只读查询。
2. `apps/web/src/pages/s2/ModelRuntimePage.tsx` 承载入口；`assetBundles/RuntimeInstallationPanel.tsx` 将 egress 缺口导航到此页。复用上一波不排队 POST/权威 GET，唯一幂等键、If-Match:0、身份二次核对、exact 内容/哈希核对，未知结果冻结。
3. 新增专项测试：限制目的主机、协议/端口/未知目的地、空字段/时间窗及 readback；相邻累计与 TypeScript；浏览器空表单验收；方案/代码复审，verification→m1 提交。

## 停止条件

- 不提交真实 host/approvalRef 选择，不做 active 策略，不启动 Runtime/Provider/商城源；不读取旧卷或重发原 12 Run。draft 不计 active 候选。
