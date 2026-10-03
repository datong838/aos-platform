# 2026-10-04｜s3o-w-ao 最新代码/当前权威卷 PG→API→Web 重启验收

按同前缀 restart plan，代码 `aos-platform/m1@b409ac51`、Alembic 唯一 head `a0v_135`，权威卷仍 `colima-aos-extension/aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927@a0v_135`。本轮未迁移、未切库、未开 Host/worker/Provider。

| 门 | 命令与实测 |
| --- | --- |
| 备份 | 新私有目录 `aos-recovery/.aos-current-backup-20261004-s3owao` 0700、`current-full.dump` 0600，4,228,768字节，SHA256 `dd3c8b9931f513c168a74a42dd587fd06741ebe0973c67a8f5b76817004e129a`；`pg_restore -l` exit0/5905行。首次 `pg_dump` 子进程已成功并 fsync 文件，但结果打印调用宿主旧 Python 不支持的 `hashlib.file_digest` 而整体命令 exit1；未再次导出，随后只读回读文件 SHA/TOC exit0。该新份尚未全库恢复；前波同一只读源的备份在独立 PG 完整恢复并做26表摘要比对。 |
| 签名安装 | 重启前后 `a0v_current_preview_http.py --signed-receipt .../.aos-current-build-pyGkqQ/signing-receipt.json` 均 exit0，`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，approved安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`、publishedVersions4、runtimeBindings0；这不是 Growth1.13 正式发布。 |
| 有序重启 | 原 Web/API `launchctl bootout` 各 exit0；8080/8434/18181 逐端口 CLOSED。`docker --context colima-aos-extension restart aos-a0v-recovery-pg` exit0，`pg_isready` exit0，源只读 `a0v_135`/Installation1/RegistryReceipt6/正式 Reader role0。原 API/Web plist `launchctl bootstrap` 各 exit0，PID49243/49259；PG StartedAt=`2026-10-03T16:50:58.347069993Z`，原命名卷未变。API 日志 `migrationMode=disabled,runtimeHost=0,workersEnabled=0`，Host inactive DISABLED。 |
| HTTP/八工作台 | 18435/8080/8434 LISTEN、18181 CLOSED；`/v1/health`、`/v1/ready`、`/openapi.json` 与 Web `/aip/skill-publish` 均200；八条 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 全200。HTTP200仅证明可达，不证明业务完成。 |
| 浏览器/业务禁入 | CUA 重载当前 in-app browser `/aip/skill-publish`：`org-org/dev-project`、37仅已评测/发布0、正式发布决定/当前 Logic/可用模型路由策略三阻断、`发布此修订` disabled、侧栏“暂无可见工作台入口”。截图 `w5cb4-e17-s3owao-browser-20261004.png`；页面只读，没有提交发布。源库再次 `BEGIN READ ONLY`：正/隔离租户 CapabilityBinding均0、正式 Reader role0。 |

当前进程按原 LaunchAgent 从最新 m1 代码路径启动，但没有正式外部 OIDC/独立 API 与 Reader/issuer 凭据；本轮未用 dev token 冒充正式 API 接受测试。生产默认 preview 的缺 Reader 禁入由同波代码 RED/43项回归证明，浏览器仍为预览栈失败封闭。首链及八工作台真实业务场景 pending。
