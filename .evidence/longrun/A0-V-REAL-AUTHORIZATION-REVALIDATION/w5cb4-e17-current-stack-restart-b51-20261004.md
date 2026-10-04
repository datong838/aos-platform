# 2026-10-04 b51 最新栈完整重启与浏览器验收

## 前置身份与边界

- `m1@3ea7c853`，代码 Alembic head `a0v_135`；当前命名卷 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`、库 `aos_current_preview_20260927@a0v_135`。当前库只读，Host/worker/Provider 关闭；不读取商城源、不重放旧 Run、不手工启动 Run。
- 独立 b25 全备 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261004-s3owaob25-XaGvdX/current-full.dump` 的 SHA256 为 `5614c2e76d4bc4abb3229461d44abb4ffa51749ddfc06f5b5f01ff29dfbbccbc`；本次重启重新校验文件与 SHA，未重复声称本次做了全恢复。b25 曾有独立全恢复/ACL/RLS 证据。
- 前后均以 `scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 检查，均 exit0、`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`：正式签名根/信任根、库版、安装与发布来源一致。当前 Growth 签名来源仍是 1.11，并非正式 Growth1.13。

## 精确重启与复核

| 步骤 | 命令或读取 | 结果 |
| --- | --- | --- |
| 停 Web→API | `launchctl bootout gui/501 /Users/ddt/Library/LaunchAgents/com.aos.a0v-web-8434.plist`，再 `com.aos.a0v-api-daily0900.plist` | 均 exit0；8080/8434 无 listener，预期停机。 |
| 重启原 PG 卷 | `docker --context colima-aos-extension restart aos-a0v-recovery-pg`；`pg_isready -U aos_app -d aos_current_preview_20260927` | 均 exit0，PG ready，18435 监听。 |
| 再做正式签名预检 | 上述 `a0v_current_preview_http.py --signed-receipt` | exit0，`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`。 |
| 启 API→Web | `launchctl bootstrap gui/501` 对应 API/Web 两个 plist；`curl http://127.0.0.1:8080/v1/ready` | 均 exit0、ready 200；新 API PID 6851、Web PID 6922。 |
| 端口与 HTTP | `lsof -nP -iTCP -sTCP:LISTEN`；读取 `/v1/health`、`/v1/ready`、八个 `/workshop/*` 路由、`/aip/skill-publish` | 18435/8080/8434 监听，18181 不监听；上述 HTTP 全 200。HTTP 200 仅证明可达，不作业务通过。 |
| 当前库只读复核 | 从签名预检确认的连接参数，在 `REPEATABLE READ READ ONLY` 事务内查询 | 库 `aos_current_preview_20260927@a0v_135`；Installation current3/active NULL/ETag3；`aip_capability_binding=0`、`extension_runtime_binding=0`、Host assignment=0，dev-org AIP registry Receipt=0。 |
| 浏览器验收 | Codex in-app browser CUA 对 `http://127.0.0.1:8434/aip/skill-publish` 调用 `getAXStateAndScreenshot()` | org-org/dev-project，37 条仅评测、已发布0；正式发布决定、Logic 版本、模型路由/策略三缺口；“发布此修订”disabled；左侧“暂无可见工作台入口”。该截图在本次 CUA 工具输出显示，未导出为独立文件。 |

第一次临时只读脚本未使用预检确认的数据库身份，查询 `alembic_version` 得 `UndefinedTable`、exit1，无写入；随后改用预检返回的确切连接参数复核 exit0。故不把第一次失败算作当前库异常。

## 结论与下一门

最新 `m1@3ea7c853` 的生产回滚守卫已随 API 重启加载；当前真实安装仍保持失败关闭。浏览器/数据库只读结果不能证明运行安装的卸载/重装或首条经营链完成。下一波 b52 审正式 RuntimeOperation 卸载/重装的合法生产者，或推进独立可信 evaluator/低权身份；当前正式身份、active Growth1.13、八配置/六 Binding 与首链仍缺。每日提醒每次送达须另执行一次完整重启。
