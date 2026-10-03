# 2026-10-03 17:29 当前全栈重启回读

- 代码 `m1@0711c7f4`；原权威 PG 命名卷 `aos-a0v-recovery-pg-data`，容器 StartedAt `2026-10-03T09:29:05.518219642Z`。API/Web LaunchAgent 重启后监听 PID 9244/9247，分别绑定 127.0.0.1:8080/8434；18181 无监听。
- `GET /v1/health`、`GET /v1/ready` 和 Web `/aip/skill-publish`、八个 `/workshop/{overview,growth,customer,merchandise,operations,finance,fulfillment,agent}` 均 HTTP 200（`urllib.request.urlopen`，exit0）。200 仅证明服务可访问。
- 签名预检沿用当前 `signing-receipt.json` 为 GREEN；当前库只读连接 `current_database()=aos_current_preview_20260927`、`session_user=current_user=aos_app`、`alembic_version=a0v_135`。独立全备 `current-full.dump` SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0`；先前 TOC 5890，本轮本机缺少 `pg_restore`，未重新核 TOC，也未做全库恢复演练。
- 浏览器 `/aip/skill-publish` 当前 `org-org/dev-project`：37 条仅已评测、已发布0；“发布此修订” disabled，页面列出正式技能放行、当前 Logic 版本、模型路由运行策略三阻断；侧栏“暂无可见工作台入口”。浏览器只读 DOM 验收，截图保存为同目录 `w5cb4-current-latest-20261003-1729-071-browser.png`（当前视口显示 37/0；完整三阻断以 DOM 快照为准）。
- 当前库只读 SQL：八类有效配置 `responsibility_plans/runtime_policies/data_policies/egress_policies/network_policies/quota_policies/budget_policies/budgets` 全0；`extension_runtime_host_assignment`、`aip_tool_binding`、`extension_runtime_binding`、`aip_responsibility_plan_head` 全0。
- 默认 BI 写入依赖内存 ASGI POST 专项回读 `503 BI_FORMAL_ISSUER_REQUIRED`，`1 passed`、exit0；未向当前 API POST。正式发行身份、签名六 Agent 来源和首链仍缺，Host/worker/Provider 保持关闭。
