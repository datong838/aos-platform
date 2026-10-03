# 2026-10-03 16:25｜BI 安装锁接线后最新栈完整重启

- 代码 `m1@baabb180`；`git diff --name-only 8c79066e..HEAD -- services/aos-api/alembic/versions` 空，代码/当前库 `a0v_135`。容器 `aos-a0v-recovery-pg` 挂载原命名卷 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`、当前库 `aos_current_preview_20260927`。
- 独立备份 `aos-recovery/.aos-current-backup-20261003-post-reboot-135/current-full.dump` SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0`，容器内 `pg_restore -l` 通过标准输入列出5890项；未恢复或改写备份。
- Web/API LaunchAgent bootout 各成功、原 PG 容器 restart 成功；第一次紧接 restart 的 `pg_isready` exit2（尚未 ready），回查原容器后 `pg_isready` accepting，签名预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN` exit0，再 bootstrap API/Web 成功。PG StartedAt `2026-10-03T08:13:08Z`，API PID3916、Web PID3918；18435/8080/8434 LISTEN，18181 无监听。API 日志新启动 `startup_extension_runtime_host_inactive code=DISABLED`。
- API `/v1/health`、`/v1/ready` 200；Web `/aip/skill-publish` 与 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 均200。API 的 `/workshop/*` 返回404是前后端地址边界，随后用 Web 端复核200，不记为工作台故障。
- Codex in-app browser 重新载入原 `/aip/skill-publish`，AX/截图见本轮工具证据：`org-org/dev-project`，37仅已评测/已发布0，正式放行事件、当前 Logic、模型路由三阻断，按钮 disabled，电商工作台暂无可见入口。
- 当前库只读 `RuntimeConfigurationCandidateReader` 八类候选全0；同租户 Plan/runtime binding/Host assignment/ToolBinding `0/0/0/0`。正式 BI issuer、锁函数和 Plan/Receipt 未在当前库安装，Host/worker/Provider保持关闭。
- 结论：最新代码与当前原卷已完整重启并失败封闭；此证据只证明健康/禁入，不证明 BI Plan 正向、八配置或自然首条经营链。未读商城源、回放旧12 Run、手工 run_definition、触碰230 L0 或 push。
