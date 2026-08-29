# AIP 剩余二十页可操作性复验

- 租户：`org-org/dev-project`
- 浏览器：Codex 内置浏览器
- 边界：无 Provider 调用、无 Secret payload、无生产派发、无真实业务写回、无发布

## 逐页结果

1. `/aip/assist`：真实历史任务可选择；上下文折叠与专注模式可切换；缺 TaskRun/AgentRun 时输入继续禁用。
2. `/aip/studio`：修复六数字同事选择竞态；六角色的 URL、选中态、标题与配置读取逐一一致。
3. `/aip/analyst`：真实只读 Order 查询返回完整 50 行、修订 1；表格、图表、地图、原始结果四视图可切换。
4. `/aip/logic`：3.5 秒内完成权威图加载；编辑/运行历史/自动化页签和 100%→110%→100% 缩放可工作。
5. `/aip/tools`：修复精确对象查询；`Order/niushop:1:1` 重启 API 后唯一命中，`total=1`，无 `niushop:1:108`。
6. `/aip/maturity`：协作预览、自动化条件和熔断降级模拟均有可观察状态变化。
7. `/aip/production-contracts`：权威差异可展开；不可满足的创建/冻结/组合门继续禁用。
8. `/aip/capabilities`：目录刷新工作；快照不可用时预检/激活诚实禁用。
9. `/aip/agent-registry`：目录刷新和运行准备刷新均重新读取；0/6 可派发未被伪造。
10. `/aip/agent-marketplace`：目录刷新可工作；不虚构未安装条目。
11. `/aip/agents`：六角色与概览/工具箱/试运行/发布分区均可切换。
12. `/aip/skill-publish`：技能选择后详情和门控信息随之切换。
13. `/aip/agent-import`：空表预检返回完整中文必填校验，无写入。
14. `/aip/capability-import`：空表预检返回完整中文必填校验，无写入。
15. `/aip/evals`：隔离契约套件运行并重读 10/10、100%、门控通过；不构成 Provider 或生产效果证据。
16. `/aip/drafts`：四状态分区、待审批条目和详情重读可工作；未执行批准或拒绝。
17. `/aip/lineage`：缺精确根引用时查询给出校验，不伪造谱系。
18. `/aip/observability`：缺 lineageId 时读取给出校验，导出保持禁用。
19. `/aip/memory-governance`：六个治理分区和权威刷新可切换/重读。
20. `/aip/doc-intelligence`：六模板可切换；修复空列表试运行静默，现明确要求先上传并选择文档，且不调用管道。

## 确定性修复

- Studio：移除双向 effect 竞态，以 URL 查询参数单向驱动实例选择；列表项改为键盘可达按钮和 `aria-pressed`。
- DocIntel：无文档时显示可行动反馈，不吞掉点击。
- Tool runtime：`query.objects` 提供 `objectId` 时按租户、类型和 ID 精确查询；前端对唯一 ID 回包做二次核验。

## 结论

本证据仅证明二十页控制面在当前开发截面可操作、真实只读链可追溯且失败关闭；不授权外部副作用、生产运行或发布。

## 累计测试

- Web：`256 files / 2328 tests passed`
- API：`test_os_substance.py 7 passed`
- Python：`tool_runtime.py compileall GREEN`
- Web production build：TypeScript + Vite `362 modules` GREEN
- `git diff --check`：GREEN
