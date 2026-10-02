# 2026-10-02 本机预览 trust 路径修正后最新全栈重启验收

## 基线及停启

- 单写分支 `m1`，重启前 HEAD `5b62ef95`；该提交与此前 `1319bbfc` 之后均无运行代码变更，`.env` 预览 trust 路径已按当前签名 Receipt 修正。原有 browser 插件/pnpm 与 test-only 未提交文件保持原样，未 `push`。
- 当前容器 `aos-a0v-recovery-pg` 挂 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；当前库 `aos_current_preview_20260927`、代码与库迁移均 `a0v_135`。当日独立备份 `aos-recovery/.aos-current-backup-20261002-cutover135/current.dump` SHA256 `8862e763347caae6c9f9ce1e15aac3e906e6770aa3c53a95bda33678863d8188`；容器内 `pg_restore -l` exit0、TOC 5621 行。首次尝试通过 stdin 列 TOC 因该工具不接受此方式报 magic 错误，改为复制到容器 `/tmp` 后验过；备份本身未改。
- `launchctl bootout` Web/API 均 exit0；确认 8080/8434/18181 无监听后 `docker --context colima-aos-extension restart aos-a0v-recovery-pg` exit0，StartedAt `2026-10-02T11:38:16.423339085Z`、卷名不变。首次 `pg_isready` exit2，紧接复查 exit0，库仍 `a0v_135`。当前签名预检 exit0：approved 安装 1、published 4、binding 0。`launchctl bootstrap` API/Web 各 exit0，新 PID `75915/75926`。

## 新鲜验收

- 18435、8080、8434 均 LISTEN；18181 无监听。`/v1/health`、`/v1/ready`、`/openapi.json` 为 200；八个 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 与 `/aip/skill-publish` 为 200，命令 exit0。
- 内置浏览器重载技能发布页并截图；`org-org/dev-project` 显示 37 项仅评测、0 发布、缺正式放行事件/当前 Logic/模型路由三项、发布按钮 disabled，左侧无电商入口。浏览器逐页打开八工作台，八页均显示“当前工作台入口不可用”“暂无可见工作台入口”；HTTP 200 不算业务可用。截图与 AX 观察保留于本次 Codex 工具记录。
- `psql -X -v ON_ERROR_STOP=1` 在 `BEGIN READ ONLY` 下 exit0：正租户安装 1，operation/binding/Host assignment/identity/Review Receipt 均 0；八类有效配置候选逐项 0。未读商城源，未写当前库、未回放旧 12 Run、未手工 run_definition、未启 Host/worker/Provider。

## 结论与下一波

本机质量预览栈已按当前 m1 运行代码及权威卷完整重启并维持失败封闭。Growth1.13 正式发布、外部 OIDC、独立身份、Host Owner/assignment、八配置与自然首链仍缺；下一波继续原 Review 生产者和八配置合法来源，正式材料到位后再接 E17 受限启动。`lsof` 组合查询 exit1 是因 18181 无监听，已从输出确认三预览端口分别在监听。
