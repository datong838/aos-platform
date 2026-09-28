# W5CB4 BG-00a｜运行策略候选 Owner 查看入口验证

- 上位方案/文件计划：同目录 `w5cb4-bg00a-runtime-policy-owner-navigation-plan-20260928.md`；当前真实库 `aos_current_preview_20260927@a0v_111` 八类配置候选均 0（`read_candidates`，READ ONLY）。这只是候选查看入口，不构成配置发布、绑定或 Host 授权。
- RED：在既有安装面板测试加入运行策略链接断言；`vitest run src/pages/s2/assetBundles/RuntimeInstallationPanel.test.tsx` exit 1，9 项中 1 fail，实际 href undefined。
- 最小实现：`RuntimeInstallationPanel.tsx` 的唯一一行候选映射指向现有 `/aip/model-runtime`，动作写为“查看当前运行策略”；没有改变按钮启用条件、配置提交或 API。
- GREEN：同专项测试 exit 0，9 passed；`tsc -p tsconfig.json --noEmit` exit 0；`git diff --check` exit 0。审查新文案仅指只读查看，原组件继续声明候选非安装绑定且运行准入由服务端复验。
- 限制：本环境无 browser-pilot 可调用工具，未做实际页面截图；当前正式实例仍缺八类配置、Host Owner 与绑定。后续 BG-00 必须从合法 Owner/审批生产正式值，经产品入口影响预览、恢复与重装验收，不能用该链接宣称业务就绪。
