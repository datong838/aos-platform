# 2026-10-03 s3o-w-ak 最新 Provider 门与原权威卷重启验收

- `m1@35ab66d4` 无新迁移；当日独立全备 `current-full.dump` SHA256 `be40a303c216324b57fc68c61b745f87e7dd2516572a43ad618954f9a71fbbcc` 回读一致，TOC5905 已可列，未做该份全库恢复演练。容器 `aos-a0v-recovery-pg` 运行于原命名卷 `aos-a0v-recovery-pg-data`；只读 DB/代码头 `a0v_135`。
- 签名 `a0v_current_preview_http.py --signed-receipt .../signing-receipt.json` 重启前后均 exit0：`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，安装 approved、publishedVersions4、runtimeBindings0。
- Web/API `launchctl bootout` → 原 PG `docker restart` exit0；紧接第一次 `pg_isready` 因启动尚未完成 exit2，未重复重启。再查 `pg_isready` exit0，库版本只读回读 exit0；原 plist `launchctl bootstrap` API/Web exit0。新 PID 43310/43312。健康/就绪、八工作台均 HTTP200，18181无监听；Host/worker/Provider仍关。
- CUA 重载 `/aip/skill-publish`：`org-org/dev-project`、37仅评测、已发布0、正式放行/Logic/模型路由三阻断、发布按钮 disabled、侧栏无可见电商入口。截图 `w5cb4-e17-s3owak-browser-20261003.png`，DOM 读回完整。真库 `BEGIN READ ONLY`：正租户 Provider/Route/CapabilityBinding/Host assignment `0|0|0|0`，dev-org Provider0。

这是新代码加载和禁入质量门，不是当前正式 Provider 或自然首链通过。历史 Provider r7 不自动迁入当前卷。
