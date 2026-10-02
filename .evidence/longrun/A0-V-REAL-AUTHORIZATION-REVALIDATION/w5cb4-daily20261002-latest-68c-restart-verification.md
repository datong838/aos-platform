# 2026-10-02 17:50 CST 最新 m1/当前权威卷完整重启复验

这是当日追加质量门，范围仍是**本机禁入预览栈**。重启时 `m1@68cde11a`（E17-a2b2a 代码 `1b9979fa` 已纳入），代码和库迁移头均 `a0v_135`。工作树有先前 browser/pnpm 改动与 test-only 文件，未触碰。

| 门 | 命令和读回 |
| --- | --- |
| 权威卷与库 | `docker --context colima-aos-extension inspect aos-a0v-recovery-pg`：运行中，`aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；容器内 `psql ... SELECT version_num FROM alembic_version`→`a0v_135`，exit0。代码 `python -m alembic ... heads`→`a0v_135`，exit0。 |
| 独立备份与签名 | 当日独立 dump `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261002-cutover135/current.dump` SHA256 `8862e763347caae6c9f9ce1e15aac3e906e6770aa3c53a95bda33678863d8188`；完整 TOC/恢复克隆证明沿用当日 cutover135 verification，本次未新建或恢复备份。`a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 重启前后 exit0，approved 安装、四 pinned 版本、binding0、代码/库135。 |
| 顺序重启 | `launchctl bootout gui/501/com.aos.a0v-web-8434`、`...api-daily0900` 均 exit0；8080/8434/18181 无监听；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` exit0；`pg_isready` 接受连接；签名预检 exit0；`launchctl bootstrap` API/Web 各 exit0。新 PG StartedAt `2026-10-02T09:50:50Z`，API/Web PID `67010/67036`。 |
| 健康和八路由 | 18435/8080/8434 LISTEN，18181 无监听。`/v1/health`、`/v1/ready` HTTP200；`/openapi.json` 首次 5 秒超时，随即 30 秒重试 HTTP200、5,340,043 bytes；八 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 与 `/aip/skill-publish` 均 HTTP200。综合 `lsof` 命令因 18181 无监听 exit1，符合预期。 |
| 页面和租户 | 内置浏览器重载技能页后 `org-org/dev-project`，37项仅评测、0正式发布、三 blocker、发布按钮 disabled、无可见电商入口。只读 SQL：`org-org/dev-project` 安装1、`dev-org` 安装0、binding/assignment/identity/operation 全0。八类配置候选仍以 15:58 当日完整检查的全0结果为准，本次未重新逐表计数。 |

结论：最新代码与当前权威卷的 PG→API→Web 重启、健康及禁入交互通过。预览 200 不代表正式启动或自然首链；正式 OIDC、三独立身份/信任根、Growth1.13 正式发布、八配置、Owner/assignment/binding 仍待补。当前真实库未写，Host/worker/Provider未启，未读商城源、回放旧12 Run、手工 Run 或 push。
