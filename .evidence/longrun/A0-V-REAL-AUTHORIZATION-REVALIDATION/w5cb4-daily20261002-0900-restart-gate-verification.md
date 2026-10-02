# 2026-10-02 09:00 最新 AOS 完整重启安全门

09:00:43 CST 自主按每日门检查；基线 `aos-platform/m1 5f7eecc7`、`AOS-001114`，m1 单写。工作树仅本波未提交方案与其他独立 browser/pnpm 文件，未对它们 add/覆盖。**结果：SAFE_BLOCKED_LATEST_FULL_RESTART；未重启或迁移当前 PG/API/Web，不能声称当日完整重启。**

| 项 | 可复核结果 |
|---|---|
| 当前数据卷/版本 | `docker --context colima-aos-extension inspect aos-a0v-recovery-pg`：自 9月30日启动，挂命名卷 `aos-a0v-recovery-pg-data`；`psql -d aos_current_preview_20260927 -Atc 'SELECT version_num FROM alembic_version'` → `a0v_118`。代码唯一新头 `a0v_135`，差17步。 |
| 新独立备份/恢复 | `aos-recovery/.aos-current-backup-20261002-daily135-preflight/current.dump` SHA256 `301e4e1ee9d3aa3deae1b31d531c3ee5ad833820437a132d1518a2c95400e3e8`、TOC5621；独立库 `aos_daily_preflight_20261002_135` 恢复/迁119…135 GREEN，克隆 `aos_runtime` schema receipt ACL 为 `SELECT=t/INSERT=f`。见 `w5cb4-daily20261002-118to135-clone-verification.md`。它不是当前库迁移。 |
| 现有进程/端口 | `ps -p 59876,65249 -o pid,lstart,command`：Web 9月30日10:58、API 9月30日11:31 启动；`lsof` 为 PG18435/API8080/Web8434 监听，18181 无监听。API 使用旧 `a0v_current_preview_http.py --signed-receipt .../.aos-current-build-pyGkqQ/signing-receipt.json`，该 receipt 为旧 `SIGNED_TREE_GREEN`，不能当本日 m1 启动证据。 |
| 现有只读探测 | `curl /openapi.json` 与 Web `/aip/skill-publish` 均 HTTP200；`curl /health` 为404（非该服务已证健康端点）。200只证明旧实例响应，不是最新栈、八工作台或核心交互验收。 |
| 安装/隔离/禁入 | 只读 SQL：`org-org/dev-project` 唯一安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` 为 approved、ETag3、无 active_revision；`dev-org` 安装0；正租户 runtime binding0、active runtime operation0、Host assignment0；`docker ... ps -a --filter label=aos.extension.owner` 空。Host/worker/Provider 未启。 |
| 新风险 | 源库 `a0v_118` 的 `extension_schema_installation` ACL 对 `aos_runtime` 为 `arwd`/INSERT=true；新代码/迁移135已在 disposable PG 修复，但尚未迁真实库。 |

不执行当前切换的精确原因：用户边界规定当前真实库只读，迁移/切换要独立波；虽已新鲜可恢复备份与完整克隆演练，仍缺零执行窗口、第二份停机一致备份、当前签名启动器/正式独立身份及迁后源/克隆全链对账。强行用代码135连接库118不满足最新版本启动条件。八工作台页面/核心交互、安装运行链、租户正反与重启后健康的正式验收均记为**未执行**，不把旧进程HTTP200或 test-only 65 passed 冒充验收。

下一安全动作：继续 GW-b-2c2c1b3b2b 的 disposable signed Growth PreparationWorker 正反链；并单列当前迁移/重启波，先核当前正式签名启动与独立角色来源及零执行窗口前置，再决定何时切换。未知外部效果只读对账；不读商城源、不回放旧12 Run、不手工 run_definition、不触碰230 L0、不 push。

## 当日后续补记（10:17 CST）

09:00 的失败关闭判定保留为当时真实状态。用户随后明确授权处理迁移和全面重启；独立波完成停机第二备份、隔离全库恢复及118→135演练、当前精确迁移、同卷PG/API/Web重启和浏览器禁入验收。见 `w5cb4-daily20261002-current-118to135-restart-{plan,verification}.md`。本机最新禁入预览栈已重启；正式受限身份与自然首链仍未通过。
