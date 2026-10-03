# 2026-10-04｜s3o-w-ao-b1 最新 Reader/issuer 接线代码原卷全栈复验

代码 `aos-platform/m1@e911d772`，Alembic 唯一 head/源库均 `a0v_135`；权威卷 `colima-aos-extension/aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927`。本轮未迁移、未写当前库、未建正式角色。

| 门 | 实测命令与结果 |
| --- | --- |
| 重启前安全门 | `shasum -a 256 aos-recovery/.aos-current-backup-20261004-s3owao/current-full.dump` 得 `dd3c8b9931f513c168a74a42dd587fd06741ebe0973c67a8f5b76817004e129a`；原份 `pg_restore -l` 已验证/5905行，本次未重复导出，也尚未完整恢复该份。`a0v_current_preview_http.py --signed-receipt .../signing-receipt.json` exit0、`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、approved Installation、publishedVersions4、runtimeBindings0。源库 `BEGIN READ ONLY` 读回135。 |
| 顺序重启 | `launchctl bootout` Web、API 各 exit0；8080/8434/18181 全关；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` exit0、`pg_isready` exit0、同一命名卷、PG StartedAt `2026-10-03T17:11:41Z`。`launchctl bootstrap` 原 API/Web plist 各 exit0，PID51474/51498。日志明确 `migrationMode=disabled,runtimeHost=0,workersEnabled=0`、Host `DISABLED`。 |
| 健康与页面 | 18435/8080/8434 LISTEN，18181 CLOSED。HTTP `/v1/health`、`/v1/ready`、`/openapi.json`、Web `/aip/skill-publish` 均200；八 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 均200。HTTP可达不等于业务首链。 |
| 当前事实 | `docker exec ... psql -X -A -t -U aos_app -d aos_current_preview_20260927 -c 'BEGIN READ ONLY; ... ROLLBACK;'` exit0：库135、Installation1、RegistryReceipt6、`org-org/dev-project`/`dev-org/dev-project` CapabilityBinding 0/0、正式 Reader/issuer role 合计0。 |
| 浏览器 | CUA 重载用户现有 `/aip/skill-publish`；刚重载时当前精确候选出现瞬时离线读失败，随后再次 AX 读回恢复：37仅评测/0发布、正式技能放行事件/当前 Logic/可用 Route+Policy 三阻断、`发布此修订` disabled、侧栏“暂无可见工作台入口”。截图 `w5cb4-e17-s3owaob1-browser-20261004.png`。无发布点击或业务写入。 |

新代码已被当前 API 进程加载，但 launchd 未配置正式两组私有身份，也没有外部 OIDC；此栈仍是禁入预览，不是正式受限 API。当前 Reader/issuer 角色切换、Owner、八类配置、六 Binding、Growth1.13 正式发布与自然首链均 pending。下一步按 D-wave 的维护 runner/完整恢复/零执行窗口独立推进，Host/worker/Provider 保持关闭。
