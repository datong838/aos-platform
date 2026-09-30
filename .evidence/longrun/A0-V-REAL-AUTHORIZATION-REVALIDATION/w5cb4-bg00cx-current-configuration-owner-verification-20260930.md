# W5CB4 BG00cx｜当前配置与 Owner 来源核验

- 基线：`m1@ee5b1c54`，`AOS-000953`；文件级方案 `w5cb4-bg00cx-current-configuration-owner-plan-20260930.md`，任务 Receipt `W5CB4-BG00CX-20260930`。
- 当前库只读：`AOS_DOTENV_DISABLED=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python` 连接 `scripts.a0v_current_preview_bootstrap._connection_parameters()`，设置 `conn.read_only=True`，对 `TenantScope('org-org','dev-project')` 调用 `runtime_configuration_candidates.read_candidates`，并查询 `alembic_version`、`meta_membership` 的 owner 数。退出 0：`aos_current_preview_20260927/a0v_118`，八类候选各 0，owner 成员 1。另只读数表：职责计划 head 0、阶段模板 head 0、档位确认 0、运行策略 head 0、网络/预算相关 head 0；AgentInstance 6 不等于合法职责计划。
- 代码合同：`routers/aip_production_contracts.py` 已向 Store 注入 `resolve_responsibility_template`；Store 创建计划仍检查精确模板、所选档位治理和 assignee。原前端“模板权威未接入”与现有代码不符。
- RED：`pnpm --dir apps/web exec vitest run src/pages/s2/ProductionContractsPage.test.tsx` 首次环境无 node 退出 127；加 bundled Node PATH 后退出 1，`1 failed/18 passed`，失败断言为新精确空态。GREEN：只改职责计划零态文案；页面/安装/配置相邻 3 文件 `38 passed`，TypeScript `tsc --noEmit` 退出 0，`git diff --check` 退出 0。
- 方案/代码复审：没有创建按钮、后端准入更改、当前库写入、Host/worker/Provider 启动、预算/审批绕过。文案只说明正式来源与禁入，不称八类配置或首链已完成。浏览器 pilot 不在本会话可用工具中，本波不记截图验收。
- 未完成：正式职责模板和所选档位治理的当前精确来源、第二 checker、八类 active 候选、Host assignment/Owner、自然首链。下一波先核当前模板/档位/assignee 的可用权威与产品入口，补最小合法来源准备链；缺外部授权时转其他独立主线。
