# W5CB4 BG-00a｜运行策略候选的当前 Owner 查看入口

## 方案复习和当前事实

231-9 BG-00 要求“过期原因→正式更新→影响预览→恢复”走产品入口，脚本不能替代。当前安装页 `RuntimeInstallationPanel` 已显示八类租户级候选，并明确非安装绑定；`ConfigurationStagePanel` 仅在当前绑定且正式来源存在时允许配置登记。当前 `aos_current_preview_20260927@a0v_111` 八类候选全 0，Host 禁入。`ModelRuntimePage` 已有运行策略当前权威只读摘要，但候选行 `runtime_policies` 的 href 是 null，用户无法沿缺项进入现有查看页。该页是核对入口，不是发布/生效入口。

## 文件级最小改动

- `apps/web/src/pages/s2/assetBundles/RuntimeInstallationPanel.tsx`：仅把“运行策略”候选的 href 指向已存在 `/aip/model-runtime`，动作命名为“查看当前运行策略”。其他候选、安装按钮、配置提交和服务端门不变。
- `apps/web/src/pages/s2/assetBundles/RuntimeInstallationPanel.test.tsx`：在既有八候选失败封闭测试中断言该链接、文案，且按钮仍禁入。不添加模拟业务成功验收。

## 退出门

专项前端测试与 TypeScript/构建适用检查；审查文案没有把租户候选冒充本安装绑定，也没有让页面 200 冒充首链。浏览器 pilot 不可用时记录未做实际 UI 截图，继续独立代码项。
