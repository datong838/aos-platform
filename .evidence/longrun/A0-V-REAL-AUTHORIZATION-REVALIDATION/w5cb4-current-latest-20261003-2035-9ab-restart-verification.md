# 2026-10-03 20:35｜本波提交后的最新 m1/原权威卷重启验收

依据同目录 `w5cb4-daily20261003-post-reboot-latest-restart-plan.md`，将预览栈从旧加载代码更新到 `m1@9ab6ed23`。真库仍只读，代码和库迁移头均 `a0v_135`，不切卷/迁移/启 Host。

| 门 | 回读证据 |
|---|---|
| 备份/签名 | 当日独立全备 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261003-1952-135/current-full.dump` SHA256 `be40a303c216324b57fc68c61b745f87e7dd2516572a43ad618954f9a71fbbcc`；`docker exec -i ... pg_restore -l < dump` 5905 行、退出0，仍未对该份做全库恢复演练。签名预检前后 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、代码/库135、approved 安装、runtime binding0，退出0。 |
| 顺序重启 | `launchctl bootout` Web/API 均退出0，8080/8434/18181 无监听（lsof 退出1）；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` 退出0，同一 `aos-a0v-recovery-pg-data` 卷、StartedAt `2026-10-03T12:34:47.870449914Z`。首次 `pg_isready` 退出2（重启瞬间尚未就绪），再次退出0后才启动 API/Web；两个 `launchctl bootstrap` 均退出0，新 PID 25621/25639，API 20:35:29 启动。 |
| 健康与禁入 | 18435/8080/8434 LISTEN，18181 0 监听；健康、就绪、OpenAPI、八工作台路径和两个 AIP 页面全200。API 启动日志 `migrationMode=disabled,runtimeHost=0,workersEnabled=0`、`startup_extension_runtime_host_inactive code=DISABLED`。 |
| 浏览器/数据库 | CUA 重载现有 `/aip/skill-publish`，org-org/dev-project，37仅已评测、已发布0，正式放行/Logic/模型路由三阻断，按钮 disabled，侧栏“暂无可见工作台入口”；CUA 截图工具输出留证。真库 `read_only=True` 查 `aos_current_preview_20260927@a0v_135`，Plan head0、runtime binding0、Host assignment0、dev-org Plan0。 |

结论是最新代码预览栈启动和失败封闭验收；不代表正式受限 API 身份、BI issuer、Growth1.13 当前 active、八类配置或自然经营首链已通过。本波不读商城源、不删库/卷/备份、不重放旧12 Run、不手工 run_definition、不 push。完整正式恢复演练和首链仍待后续合法来源。
