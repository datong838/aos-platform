# W5CB4 BG-00b｜技能发布来源与绑定入口诚实性验证

## 权威与当前库

复习 231-1/9、AIP 前台中文展示军规 52、`SkillPublicationOptionsReader`、`SkillPublishPage` 和两个绑定 preview/command 合同。当前 `aos_current_preview_20260927@a0v_111` READ ONLY 查询：37 evaluated Skill、0 published Skill、10 published Capability、6 AgentInstance、0 SkillBinding；`org-org/dev-project` 的 release decision/publication event、Logic publication、ModelRoute Head、RuntimePolicy Head 各 0。发布候选不足，不能先以任意请求方 exact ref 做绑定。

## RED→GREEN

- 增补现有发布页测试：三阻断须中文说明并指向实际 Logic/模型路由查看页；未知阻断保留审计代码；原“打开权威绑定流程”须如实改为只读状态页。`vitest run src/pages/s2/SkillPublishPage.test.tsx` exit 1，4 项中 2 fail，复现英文代码裸露及虚假入口。
- 最小修改仅在 `apps/web/src/pages/s2/SkillPublishPage.tsx`，映射三已知 blocker、保留未知审计代码，把无效 `intent=bind` 链接改成只读组织绑定状态并明示创建入口待接线。没有改服务端门、发布请求、绑定命令、预算、当前库。
- `vitest run src/pages/s2/SkillPublishPage.test.tsx src/pages/s2/assetBundles/RuntimeInstallationPanel.test.tsx --silent` exit 0，13 passed；`tsc -p tsconfig.json --noEmit` exit 0；`git diff --check` exit 0。现有正向选取测试仍证明只有三个精确选项被选择后才可提交，未知/缺项零 POST。

## 复审及限制

前台指导不产生正式 release event、Logic publication 或 ModelRoute；不能把 37 evaluated Skill 当 37 published。现无正式 SkillBinding/ResponsibilityPlan、八运行配置候选 0、Host/Provider 关闭，首链待证。没有 browser-pilot 可调用工具，未做浏览器截图。下一波对准 release decision/publication event 的正式产品来源，再做首链必要 Logic/Route 发布及绑定预检；不能先批量冲 37 Skill。
