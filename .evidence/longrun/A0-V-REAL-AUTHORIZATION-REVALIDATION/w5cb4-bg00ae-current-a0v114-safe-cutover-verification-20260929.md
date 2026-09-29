# W5CB4 BG-00ae｜当前卷 a0v114 可恢复切换验证

## 进入身份与零执行窗口

- 进入 HEAD `m1@539fbacd`，工作区只另有浏览器插件/`pnpm-lock.yaml` 和两份 w5c8i test-only 未提交现场，本波不触碰。PG 容器 `aos-a0v-recovery-pg` Running，挂载 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`，端口 18435；当前库 `aos_current_preview_20260927@a0v_113`。迁移前 `scripts/a0v_current_preview_http.py --signed-receipt ...` 退出 0，`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`：approved 安装 1、published bundle 4、Runtime Binding 0，签名根/Receipt 指向当前 `.aos-current-build-pyGkqQ`。
- 源表基线（count/MD5 of sorted JSONB）：`bundle_installation` 1/`c5b39b87febbbb6a1555a77b1d610941`、`bundle_installation_revision` 3/`47d9fb0b02235dbb62bd9b348e5b63d6`、`asset_bundle` 4/`7bee66cc102ab8dd0df6da8f9640a0c8`、`asset_bundle_version` 4/`b8144ee0e2a2f9ce6b233e8fb2bbe2fc`。四张 Eval authority 表均 0。
- `launchctl bootout gui/501 /Users/ddt/Library/LaunchAgents/com.aos.a0v-web-8434.plist`、旧 API PID 55894 `SIGINT` 均退出 0；8080/8434/18181 `lsof` 无监听（退出 1），当前库 `pg_stat_activity` other_sessions=0，形成零执行窗口。Host/worker/Provider 未开。

## 新备份、全库克隆与迁移

- 新 custom dump `/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260929-bg00ae-cudpdml8/aos_current_preview_20260927_a0v113.dump`：`pg_dump` 退出 0，3,942,437 字节，SHA256 `2c6751ecbb6c7335e4db9059cd2c7d5ab82dd266eed5e5df4ab325936ae619c0`，test-only `pg_restore --list` 退出 0、TOC 5594。目录 0700，原库/卷/备份保留。
- 新 test-only 库 `aos_bg00ae_cutover_20260929` 用该 dump `pg_restore --no-owner --single-transaction --exit-on-error` **保留 ACL** 全库恢复，退出 0；恢复前版 a0v113，四个安装/制品 count/MD5 与上述基线逐项相等，四 Eval 表均 0，原 default ACL `aos_runtime=arwd/aos_app` 得到保真复现。
- 新克隆 a0v113→114 Alembic 退出 0；sidecar 0 行、RLS/FORCE=true、`aos_runtime` SELECT/INSERT=true、UPDATE/DELETE=false，旧 Receipt INSERT=false；四个旧摘要未变。预览版本门测试先 RED `1 failed, 2 passed`（预期114/实113），最小改 `scripts/a0v_current_preview_http.py` 与专项测试后 `3 passed`，退出 0。
- 再读零窗口 8080/8434/18181 均无监听、当前库 other_sessions=0 后，当前库 Alembic a0v113→114 退出 0；四个旧摘要逐项不变，五张 Eval/sidecar 表均 0，sidecar 权限同克隆。无业务行写入。

## 最新栈回读与限度

- 新代码签名预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`（a0v114、approved1、published4、binding0）退出 0；API 新 session `13697` 的启动日志包含 `runtime_host_inactive code=DISABLED` 与 worker disabled，Web LaunchAgent 重新 bootstrap 退出 0。PG 仍挂载权威卷；`lsof` 显示 18435/8080/8434 LISTEN，18181 无监听（组合 `lsof` 退出 1 因该端口缺席）。
- `curl` 对 API `/v1/health`、`/v1/ready`、`/openapi.json` 全部 HTTP 200；Web 八路 `/workshop/cockpit`、`content-campaign`、`operations`、`creator-growth`、`media-studio`、`analyst`、`price-governance`、`customer` 和 `/aip/skill-publish`、`/aip/agent-catalog` 全部 HTTP 200，命令退出 0。只读租户 canary：`bundle_installation` 在 `org-org/dev-project` 为 1，`dev-org/dev-project` 为 0。无 browser-pilot 工具，本波无截图/交互验收；HTTP 200 不证明经营链。

BG-00ae 只完成可恢复迁移与最新栈基础检查。正式 G2 issuer/Owner/内容与 S3 仍缺，Skill guard/Host/worker/Provider 继续关闭；sidecar 同事务 writer/Report/Gate consumer、自然首链、恢复/卸载重装、八工作台真实业务和发布决定均待后续真证据。下一波 BG-00af 先方案后 RED 做同事务 proof 写入/读取，不触发旧 12 Run、手工 run_definition 或商城源。
