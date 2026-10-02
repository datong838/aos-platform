# 2026-10-02 E17 资源证据修复后最新代码完整重启

## 预检与顺序停启

- 单写 `m1@753d3a4a`，代码 Alembic `a0v_135 (head)`，当前库 `aos_current_preview_20260927@a0v_135`。原有 browser 插件/pnpm 和历史 test-only 未提交文件未纳入本波。权威容器 `aos-a0v-recovery-pg` 保持命名卷 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`。
- 当日独立备份 `aos-recovery/.aos-current-backup-20261002-cutover135/current.dump` SHA256 `8862e763347caae6c9f9ce1e15aac3e906e6770aa3c53a95bda33678863d8188`；容器 `pg_restore -l /tmp/aos-current-20261002-cutover135.dump | wc -l` 为 5621 行、退出0；完整恢复克隆沿当日 cutover135 verification。本次无迁移、无库写入。
- 重启前后 `a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 均退出0：`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、库/代码135、approved 安装、published4、binding0。它是 pinned 预览来源，不是 Growth1.13 正式发布授权。
- `launchctl bootout gui/501/com.aos.a0v-web-8434` 与 `...api-daily0900` 各退出0，8080/8434/18181 停止监听；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` 退出0，StartedAt=`2026-10-02T12:17:01.62663736Z`，原卷不变；`pg_isready` 退出0、库135。随后 `launchctl bootstrap` API 与 Web 各退出0，新 PID `78897/78899`。18435/8080/8434 监听，18181 无监听；组合 `lsof` 退出1只因18181关闭。

## 新鲜回读

- `/v1/health`、`/v1/ready`、`/openapi.json`、`/aip/skill-publish` 与八个 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 均 HTTP200，命令退出0。
- Codex 内置浏览器重载技能发布页：`org-org/dev-project`，37 项仅评测、0 发布，缺正式发布放行事件、当前 Logic、可用模型路由三 blocker，发布按钮 disabled，侧栏无可见电商入口；截图与 AX 状态见本轮工具输出。逐页访问八工作台，八页均显示“当前工作台入口不可用”和“暂无可见工作台入口”。页面可达不等于业务可用。
- 当前库只读事务按签名连接回读：八类有效配置候选均 0；正租户安装 1、operation0、binding0、Host assignment0、Host identity0。Host/worker/Provider 没有开启，未读商城源、未回放旧12 Run、未手工 `run_definition`，未触及 230 L0。

## 判定

最新运行代码与权威数据卷的本机预览质量门 GREEN 且业务仍安全禁入；正式 OIDC、独立身份、Growth1.13 正式发行、八配置、同代绑定/精确 Owner 和自然首链均待证。下一波继续正式 Owner 和八配置合法来源，外部材料缺失仅阻断当前实例。
