# 2026-10-03 重启后最新 m1/权威卷全栈复验

## 执行与结果

- `m1@93a6e4f7`，代码唯一 Alembic 头 `a0v_135`；`docker --context colima-aos-extension exec aos-a0v-recovery-pg psql -U aos_app -d aos_current_preview_20260927 -Atc 'SELECT current_database(), version_num FROM alembic_version'` 回 `aos_current_preview_20260927|a0v_135`，退出0。原命名卷 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data` 保持。
- `services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 在重启前后均回 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、当前安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`、publishedVersions4、runtimeBindings0，退出0。此预览签名不等于 Growth1.13 正式身份。
- 独立完整备份 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261003-post-reboot-135/current-full.dump`：`pg_dump -Fc`、SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0`，`pg_restore -l` 退出0，TOC 5905 项，ACL 811 项。首次 `current.dump` 用 `--no-owner --no-acl`，SHA `2bae899191169225849cb8e2d26850711c2436220b0d2e5870efaa8d665e125c`、TOC5094，不作为完整权威备份；两份均保留。今日完整备份只完成 TOC 校验，未再做全库恢复演练；昨天相同迁移版本备份有独立恢复演练。
- `launchctl bootout gui/501/com.aos.a0v-web-8434` 与 `...api-daily0900` 退出0；等端口关闭后 `docker --context colima-aos-extension restart aos-a0v-recovery-pg` 退出0。容器 `StartedAt=2026-10-02T18:59:26.719507011Z`，`pg_isready` 退出0，版本仍135。`launchctl bootstrap` 原 API/Web plist 均退出0；新 API PID26604、Web PID26606，进程启动 2026-10-03 02:59:56 CST。
- 18435/8080/8434 LISTEN，18181 CLOSED。API 启动日志回 `migrationMode=disabled`、`runtimeHost=0`、`workersEnabled=0`、`startup_extension_runtime_host_inactive code=DISABLED`。`/v1/health`、`/v1/ready`、`/openapi.json` 与八个 `/workshop/*`、`/aip/skill-publish`、`/aip/agent-catalog` 二次 HTTP 验证全200，命令退出0。首次 5 秒冷 OpenAPI 生成超时，30 秒复查成功；不将首次失败抹掉。
- 当前库只读查询退出0：八类配置候选均0；org-org/dev-project 安装1，dev-org安装0；runtime binding、Host assignment、Host identity 各0。未执行迁移、切库、Run、Host、worker、Provider 或商城源读取。
- 浏览器 CUA 刷新 `/aip/skill-publish`：37 已评测、0 已发布，缺正式放行事件、当前 Logic 发布版、可用 Route/Policy 三阻断，发布按钮 disabled；左侧电商工作台“暂无可见工作台入口”。截图 `w5cb4-daily20261003-post-reboot-skill-publish.png`。首次页面尚在加载时显示“目录读取失败/候选读取失败”，刷新稳定后为上述禁入状态，未据首次瞬态判业务故障。

## 判定及下一波

重启后最新 m1 预览栈和当前权威卷健康、禁入维持；正式受限 API/三身份/八配置/Host/自然首链仍未齐。继续 E17-s3g 原 Budget/Quota/BudgetPolicy 合法生产者与审批边界的隔离代码链。当前真库只读，Goal active。
