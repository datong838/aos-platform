# W5CB4 当前出站策略产品入口 verification（2026-09-27）

## 结论与边界

- 已在 `/aip/model-runtime` 增加出站策略草稿入口，并将安装候选中的 egress 缺口导航到此页。本波没有提交出站策略、没有 active 修订、没有网络流量或 Provider 调用。
- 当前新建入口只提供 `api.agnes-ai.cn`，且用户须主动选择；历史 apihub 主机虽仍被后端旧修订合同识别，但本入口不作为新策略选项。HTTPS/443、`allowPublicFallback=false`、未知目的地 block 固定；draft 的 regionState=`unknown`、region=null，不能据此真实出站。owner、approvalRef、有效窗都留空待合法输入，approvalRef 字段不等于审批已核验。
- 唯一 POST 带一次性幂等键和 `If-Match:0`，不进入离线队列；POST/GET 两次响应后各重核身份，精确比较租户、内容、哈希。未知结果只读对账，不能换键重发；已有策略 ID 只读查询、不覆盖。

## 验证

- 前端专项/相邻 Vitest：新 Egress 3、Data 3、RuntimeInstallationPanel 8、ModelRuntimePage 6、API client 4，共 24/24 通过；TypeScript `tsc --noEmit` 通过；`git diff --check` 通过。
- 浏览器 `http://127.0.0.1:8434/aip/model-runtime` 实见当前主机默认“请选择”、唯一 `api.agnes-ai.cn` 选项、draft 与地域未知说明；空表单点击创建只显示“策略 ID、负责人和正式审批引用均须明确填写”。无 POST、无真实审批或地域输入。
- 同页仍显示跨页投影 `ecommerce agent definitions differ from 6-role authority`；本波未修改该独立阻断。运行链依然 0 路由、0 供应商，不可试聊。

## 下一波

- 下波先诊断六角色投影与当前安装/Agent 定义的 exact 差异，判断是预览环境缺当前配置还是代码缺陷；只读定位后再形成文件级修复计划。不得把无绑定的工作台显示成可用，也不因三张草稿入口存在就宣称八项配置已完成。
- BudgetPolicy 仍先要求 active BudgetRevision；P2g30b Action 正向 producer 仍要求健康绑定。原 12 Run、商城源和旧数据卷均未触碰。
