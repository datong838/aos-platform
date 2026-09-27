# W5CB4 BG-00 E01a：技能发布精确只读候选后端证据（2026-09-28）

## 结论

**E01a 后端只读候选合同通过，E01b 前端选择仍待施工。** 新 `GET /v1/aip/skills/{skill_id}/revisions/{revision}/publication-options` 按认证租户只读给出候选，不创建审批、发布、绑定或路由。Release 候选须 exact Skill Eval target、passed 且未失效/未过期，并且该 publication 没有撤销/停用/弃用等后续事件；Logic 是同租户已发布 exact revision；Route 经现有运行权威检查。多候选全部保留供显式选择，不自动选“最新”；最终 POST 仍由原 `AipSkillPublicationService` 现时复核并写 Receipt。

## 验证与现时边界

- RED：新增路由测试首次因共享 `client` fixture 指向已不存在的历史 2026-09-13 allowlist 目录在 setup ERROR，未执行测试；改用路由函数直接注入、保留 OpenAPI 路径断言后得到预期 `AttributeError: publication_options`。随后最小实现；服务负例覆盖空候选/缺 Skill、同租户、只读 SELECT、撤销后无候选，正例覆盖 exact gate/event/Logic/active route。
- 专项 `test_aip_skill_publication_options.py` 与发布/绑定邻接：`15 passed, 8 warnings`；D01/原链/Task/AgentRun 扩展累计 13 文件：`124 passed, 8 warnings`；新模块与路由 `compileall`、`git diff --check` 通过。未有真实当前库 GET 回读，不将单元结果报作当前发布成功。
- 浏览器只读打开 `/aip/skill-publish`：当前工作区 37 个仅已评测技能、0 个已发布，页面仍出现“发布事件 ID”等自由输入框。这是 E01b 的确切产品缺口；E01a 不改前端、不发 POST。

## 下一步和风险

E01b 把十项手填替为当前候选显式选择、只读刷新和提交前确认；候选为 0 时导航到已有评测/Logic/模型配置 Owner，不填默认值。随后用最新代码重启安全 8080、当前卷仍 a0v_106 并读回 GET 的空候选，确认 18181/worker 关闭。候选列表是建议而非授权，查询后到 POST 之间漂移仍须由原 Owner 拒绝；当前没有模型路由/预算/发布事件，不能据此激活任何 Agent。
