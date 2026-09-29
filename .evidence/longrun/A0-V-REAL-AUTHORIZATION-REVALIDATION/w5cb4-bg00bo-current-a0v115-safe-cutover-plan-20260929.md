# W5CB4 BG-00bo｜当前权威卷 a0v115 可恢复迁移与最新栈重启方案

## 上位方案、身份和边界

按 AGENTS.md、aos-engineering-delivery、231/231-5/231-9、E17 当前真库只读迁移独立波、BG-00ae 已验证切换流程与 BG-00bn `a0v_115` 克隆证据。进入 m1 唯一写者，当前 PG `aos-a0v-recovery-pg-data`→`aos_current_preview_20260927@a0v_114`，签名 Receipt `.../.aos-current-build-pyGkqQ/signing-receipt.json`，预检 approved1/published4/binding0。目标只迁移至115并用最新 m1 重新启动数据库、API、Web；Runtime Host/worker/Provider/18181 继续关闭。旧12 Run、商城源、手工 run_definition 均不触碰。

## 文件级与步骤

1. 更新 `scripts/a0v_current_preview_http.py` 的精确预检 schema head `a0v_114`→`a0v_115`，先改 `services/aos-api/tests/extension_runtime/test_a0v_current_preview_http.py` RED 再最小实现；保留签名/安装/binding 检查逻辑。
2. 定位现有 API PID 与 Web LaunchAgent，关闭 API `SIGINT`、Web `launchctl bootout` 防 KeepAlive；核 8080/8434/18181 无监听、PG 当前库 other sessions=0、Host/worker/Provider 未开，建立零执行窗口。停机后重新取当前库独立 custom dump，0600、SHA256/字节/TOC，不覆盖 BG00bn dump。
3. 新建第二 test-only DB，用本波停机后 dump `pg_restore --single-transaction --exit-on-error` 全库恢复；核源/克隆114、安装/制品/绑定及表数；在克隆升级115，五固定 ID runtime 写拒绝、普通写可回滚、安装/制品不漂移；保留 clone/backup，不删除。
4. 再核零执行窗口与 source114 后，仅对精确当前库执行 Alembic 114→115；回读 trigger、元数据0、安装/制品/binding，源 dump可恢复。迁移无业务行写入。重启同一命名卷 PG 容器并读挂载/库头；用最新 m1 签名预检后启 API、Web；readback 18435/8080/8434，18181 无监听、health/ready/openapi、八工作台+AIP 关键路、正租户安装与负租户 canary。浏览器仅 browser-pilot 可用时截图交互；页面200不算首链。
5. 后端专项/邻接与预检回归、代码/方案复审、verification、m1 精确提交、01/06、D-waves、authority/Prime 同步。迁移后若任何步骤失败，先隔离和只读对账；不删除源库/卷/备份或重放未知。

## 完成判据

源 PG 精确 `a0v_115`、原安装/制品/binding 读回不变，备份/第二克隆证明可恢复、最新 HEAD API/Web 页面可达、Host/worker/Provider/18181 关闭；正式元数据 Producer/策略 active/首链仍 pending。
