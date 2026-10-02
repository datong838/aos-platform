# 2026-10-02 最新 m1@1319bbfc 当前权威卷完整重启复验

本次按用户已授权的完整质量门，在 d2b3c4f 回执读回代码提交后执行；范围为本机**禁入预览栈**，不把 HTTP200 计为经营首链。

| 门 | 新鲜输出 |
| --- | --- |
| 写者与代码 | `git branch --show-current` 为 m1，HEAD `1319bbfc`；工作树原有 browser/pnpm 与 test-only 未提交现场均未触碰。代码 `alembic ... heads` 为 `a0v_135`。 |
| 权威卷、库、备份 | 容器 `aos-a0v-recovery-pg` 运行并挂 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；库 `aos_current_preview_20260927` 只读查 `alembic_version=a0v_135`。独立 `aos-recovery/.aos-current-backup-20261002-cutover135/current.dump` SHA256=`8862e763347caae6c9f9ce1e15aac3e906e6770aa3c53a95bda33678863d8188`，`pg_restore -l` exit0、TOC 5621 行；其完整恢复演练沿当日 118→135 记录。 |
| 停启顺序 | `launchctl bootout` Web/API 后端口不再监听；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` 后 StartedAt=`2026-10-02T10:46:11.893226845Z`，第一次 `pg_isready` exit2，随即有界复查接受连接、库仍135；当前签名预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`/published4/binding0；`launchctl bootstrap` API/Web 各 exit0，新 PID `72311/72313`。 |
| 健康、路由与禁入 | 18435/8080/8434 监听，18181 无监听；API `/v1/health`、`/v1/ready`、`/openapi.json` 200，八个 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 和 `/aip/skill-publish` 均200。内置浏览器 reload 后仍37项仅评测/0发布、三 blocker、按钮 disabled、电商无可见入口。 |
| 当前实例只读对账 | `BEGIN READ ONLY`：正租户 installation1、dev-org installation0；operation/binding/assignment/identity/Review Receipt 均0；八有效配置候选按原查询谓词逐项 `0|0|0|0|0|0|0|0`。 |

`/health` 曾返回404，已按既有 API 合同 `/v1/health` 复核200；重启 shell 中以 `path` 作循环变量覆盖了 zsh 的特殊 PATH，首个路由命令 exit127，改用绝对命令路径后全项复验 exit0。没有当前真库业务写、商城源读取、旧12 Run重放、手工Run、Host/worker/Provider启用或 push。正式 OIDC/签名信任/独立身份、八配置、Growth1.13 当前发行、Owner/assignment/binding 与自然首链仍未完成。
