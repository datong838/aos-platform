# 2026-10-03 s3o-w-ai 最新代码与原权威卷完整重启验收

- 运行代码：`m1@43268b14`，数据库代码头与真实库均 `a0v_135`。`shasum -a 256` 当日独立全备 `current-full.dump` 为 `be40a303c216324b57fc68c61b745f87e7dd2516572a43ad618954f9a71fbbcc`；此份 TOC5905 曾通过，只验证可列目录，未做全库恢复演练。
- 重启前 `a0v_current_preview_http.py --signed-receipt .../signing-receipt.json` 退出0：`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，原库 `aos_current_preview_20260927`、approved 安装、publishedVersions4、runtimeBindings0。`docker inspect` 原 PG 挂载命名卷 `aos-a0v-recovery-pg-data`。
- `launchctl bootout` Web/API → `docker --context colima-aos-extension restart aos-a0v-recovery-pg` → `pg_isready` 和 `BEGIN READ ONLY` 版本回读 → 原 plist `launchctl bootstrap` API/Web，各步骤退出0。新 API/Web PID39908/39910；签名预检复跑退出0，`/v1/health`、`/v1/ready`、`/openapi.json` HTTP200，八条 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 均200，18181关闭。
- Codex in-app browser CUA 重载 `/aip/skill-publish`：`org-org/dev-project`、37仅评测、已发布0、正式放行/Logic/模型路由三阻断、发布按钮 disabled，侧栏无可见电商入口。截图 `w5cb4-e17-s3owai-browser-20261003.png`；DOM 读回与页面状态一致。只读 DB 复核 CapabilityBinding/active AgentInstance/Plan/Host assignment 为 `0|0|0|0`，退出0。
- 八路由第一条验收命令因在 zsh 循环误用特殊变量 `path`，导致子 shell 的 PATH 被覆盖、`curl` 找不到，退出1；改用 `route_name` 原样复验八路由及 OpenAPI，退出0。没有修改服务或数据库来掩盖这次命令错误。

此质量门证明新代码已经加载且禁入仍正常，不证明正式预算来源、Host 授权、六绑定或自然经营首链。当前真实库保持只读，Host/worker/Provider关闭。
