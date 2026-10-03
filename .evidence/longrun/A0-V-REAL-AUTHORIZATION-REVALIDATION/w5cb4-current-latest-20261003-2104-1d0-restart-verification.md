# 2026-10-03 21:04｜s3o-w-ae 提交后最新代码/原卷重启验收

依据 `w5cb4-daily20261003-post-reboot-latest-restart-plan.md`，将禁入预览从旧进程更新至 `m1@1d085703`。当前真库只读，不迁移、不切卷、不启 Host/worker/Provider。

| 门 | 实测与退出码 |
| --- | --- |
| 身份、版本与备份 | `git branch --show-current`=`m1`，HEAD `1d085703`；`services/aos-api/.venv/bin/python scripts/a0v_current_preview_bootstrap.py` 退出0，库 `aos_current_preview_20260927@a0v_135`。HTTP 签名预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、代码/库135、approved 安装、runtime binding0，退出0。当日独立全备 SHA256 `be40a303c216324b57fc68c61b745f87e7dd2516572a43ad618954f9a71fbbcc`、TOC5905，校验退出0；该份尚未全库恢复演练。 |
| 有序重启 | Web/API `launchctl bootout`→`docker --context colima-aos-extension restart aos-a0v-recovery-pg`→`pg_isready`→API/Web `launchctl bootstrap` 均退出0。卷仍 `aos-a0v-recovery-pg-data`，PG StartedAt `2026-10-03T13:04:29.863054805Z`，新 API/Web PID 27591/27594。18435/8080/8434 LISTEN，18181 无监听。API 日志 `startup_extension_runtime_host_inactive code=DISABLED`，worker disabled。 |
| 路由与页面 | `/v1/health`、`/v1/ready`、`/openapi.json` 均200；八条 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 与两条 `/aip/{skill-publish,agent-catalog}` 均200。首次误查 `/health`、`/ready` 得404，OpenAPI 核对实际路径后复验200；这是路径误用，未作代码修复。 |
| 浏览器与只读库 | CUA 重载用户已有 `/aip/skill-publish`：org-org/dev-project、37项仅已评测、已发布0、缺正式放行/Logic/模型路由，发布按钮 disabled，侧栏无可见电商工作台入口；CUA 输出含页面截图。只读事务查询当前 Plan head、runtime binding、Host assignment 在 org-org 与 dev-org 均0；org-org 六个 AgentInstance 均 `provisioning`，active0。 |

结论：最新 m1 预览可达且失败封闭；真实正式身份、八类配置、Growth active 和自然首链未通过。没有读取商城源、重放旧 Run、手工 run_definition、写当前库或推送。下一波 s3o-w-af 验证真实不同 UID 的私有连接和正式身份来源。
