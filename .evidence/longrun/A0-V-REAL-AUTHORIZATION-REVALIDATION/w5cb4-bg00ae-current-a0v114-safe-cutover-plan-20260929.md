# W5CB4 BG-00ae｜当前权威卷 a0v114 可恢复切换方案

## 进入事实与硬门

BG-00ad `m1@539fbacd` 代码唯一 Alembic head `a0v_114`，仅在 test-only ACL 保真克隆 GREEN；当前权威库 `aos_current_preview_20260927@a0v_113`，运行 API/Web 是迁移前启动基线。按每日最新重启硬门，必须先安全切换，不强行用新代码重启。延续 BG-00z 两轮经验：当前 `aos_app/public/table` 默认 ACL 曾令新表继承 `aos_runtime=arwd`；克隆必须保留 ACL，迁移必须显式撤权并回读。真库只允许本独立波在备份/克隆/零窗口各门通过后迁移；不删库卷备份。

## 预定精确变更

- 可能修改 `scripts/a0v_current_preview_http.py` 及其版本门测试的预期 a0v113→114；须先在代码/当前差距消除后启动。
- 本波证据 `.evidence/.../w5cb4-bg00ae-current-a0v114-safe-cutover-{plan,verification}-20260929.md`，docs 306/D-waves/authority；无业务逻辑新接线。当前库迁移仅 Alembic a0v114 sidecar 与索引。

## 有界顺序/退出

1. 核 m1 HEAD/唯一写者/工作树、当前 PG 容器挂载 `aos-a0v-recovery-pg-data`、库 a0v113、签名 Receipt/安装状态、端口/Host、正式四表空；确认最新迁移结构 `a0v_114`。若身份漂移停止切换。
2. 停 API 和 Web（launchd bootout，防 keepalive 复活）；确认 8080/8434/18181 无监听、无其他执行连接。使用当前卷当前库新做独立 PG custom dump，记录 SHA256/字节/TOC 且可列目录；备份保留不覆盖。
3. test-only PG 新建唯一库，`pg_restore --no-owner --single-transaction --exit-on-error` **保留 ACL** 全库恢复；回读 a0v113、关键安装/制品计数和摘要、四 Eval 表空/权限。迁移 clone 到114，回读 sidecar RLS/FORCE、ACL `SELECT,INSERT` 且无 UPDATE/DELETE、空表及旧摘要不变；专项/相邻回归。
4. 仅若 1-3 全 GREEN 且零执行窗口持续，迁移当前库 113→114，回读安装/摘要/新表权限。更新版本门与最小测试；最新 m1 启 API/Web，读回 PG 卷/库/版本、签名 preflight、8080 health/ready/openapi、8434 八工作台与 AIP 页、18181/Host/worker/Provider 关闭。浏览器仅有 browser-pilot 才做截图交互；HTTP 200 不算首链。
5. 任一门失败，保留备份和当前现场，停止当前迁移/重启，诊断后最小修复/重验；未知业务效果只读对账，绝不重发旧 Run 或手工 run_definition。真库仍未有正式 G2 authority；Skill guard 不解除。
