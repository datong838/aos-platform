# 2026-09-29 09:04 最新 m1 与当前卷整栈重启检查

## 前置身份

- 北京时间 09:04，`m1@6a3bff813a761d2d3f29bfae0f55fca6b02fea7a`；原有浏览器插件、锁文件和测试的他人工作树差异保持原样，未纳入本次提交、不 push。
- 重启电脑后 Colima 三 profile 均 Stopped，PG/API 无监听，Web 8434 为 launchd 新进程。先启动 `colima --profile aos-extension`，再启动原 `aos-a0v-recovery-pg` 容器。Docker inspect 回读运行中、挂载 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；`pg_isready` 接受连接。
- 代码迁移头 `a0v_111`（`services/aos-api/alembic/versions/a0v_111_budget_active_insert_gate.py`）；容器内 READ ONLY 查询为 `aos_current_preview_20260927@a0v_111`。签名 Receipt 路径 `/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 的当前代码预检退出 0、`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`：安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` approved、四个 signed bundle published、Runtime Binding 0。
- 昨日独立备份 `/Users/ddt/work/projects/ai_agent/.aos-daily-backup-20260928-latest-4EQ82N/aos_current_preview_20260927_a0v111.dump` 的 SHA256 重算为 `22c4e263ae11ab578fc73be3ff61272bf731bb1c74d355c348c4c510bc1b42fd`，容器内 `pg_restore --list` 5551 行。今日另以当前库只读 `pg_dump -Fc` 生成 `/Users/ddt/work/projects/ai_agent/.aos-daily-backup-20260929-oXxcWz/aos_current_preview_20260927_a0v111.dump`，0600、3,917,396 字节、SHA256 `e527a55cbe5fca5b32754ac08257d3d1908a895ac16b68103794d3830e868b3d`、TOC 5551 行。今日归档尚未做全库恢复演练，不能声称已证明可恢复。

## 启动与读回

- 当前 `scripts/a0v_current_preview_http.py --serve` 启动 API 8080（PID 8278），日志明确 `migrationMode=disabled`、`runtimeHost=0`、`workersEnabled=0`、`startup_extension_runtime_host_inactive code=DISABLED`。Web launchd `com.aos.a0v-web-8434` 精确 kickstart，PID 从 4160 变为 8355，工作目录为当前 m1 的 `apps/web`。PG 18435 为原容器转发；18181 无监听。
- `curl`：8080 `/v1/health`、`/v1/ready`、`/openapi.json` 各 200；8434 `/workshop/cockpit`、`/workshop/content-campaign`、`/workshop/operations`、`/workshop/creator-growth`、`/workshop/media-studio`、`/workshop/analyst`、`/workshop/price-governance`、`/workshop/customer`、`/aip/skill-publish`、`/aip/agent-catalog` 均 200。Vite 路由 200 仅证明服务可达，不能证明页面渲染、交互或业务可运行。
- 容器内 `psql -U aos_app -d aos_current_preview_20260927` 的 `BEGIN READ ONLY` 查询后 ROLLBACK：同租户 `org-org/dev-project` AgentInstance 6、SkillBinding 0、CapabilityBinding 0；Skill evaluated 37、published 0；Runtime Binding 全库 0。未读商城源和业务明细，未执行 Run、Provider 或外部动作。

## 限制与恢复入口

本会话无 `browser-pilot` 工具，未编造截图或八页面交互验收。正式 Skill Eval/发布、配置、Host assignment/Owner、预算审批与自然首链仍未完成。每日检查结束立即继续 BG-00g：从已提交 RED `m1@6a3bff81` 实现 exact SkillBinding 评估/激活产品入口；当前库保持只读，Host/worker 关闭。
