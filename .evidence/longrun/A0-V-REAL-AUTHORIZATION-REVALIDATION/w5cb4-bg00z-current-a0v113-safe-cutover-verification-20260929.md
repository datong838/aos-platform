# W5CB4 BG-00z｜当前卷 a0v_113 安全切换与 ACL 修复验证

方案 `w5cb4-bg00z-current-a0v112-safe-cutover-plan-20260929.md`，最终版本以其 14:53 修订门为准。基线 `m1@4904cced`、authority `AOS-000874`；最终运行代码 `m1@d95d4043`。本波只做当前卷 schema 安全切换及独立 Eval 四表权限修复，不造正式身份、Receipt 或 Run。

## 零执行窗口与两次独立备份

- 原 API session `3540` Ctrl-C 退出 0；Web 8434 是 keepalive LaunchAgent `com.aos.a0v-web-8434`，单纯 TERM 后自动重生，随后 `launchctl bootout gui/501 ...plist` 退出 0。`lsof` 回读 8080/8434/18181 无监听（各退出 1），当前库其他连接数 0、版本 `a0v_111`。Host/worker/Provider 一直关闭。
- 首份当前库 custom-format serializable dump `/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260929-bg00z-mWNpL0/aos_current_preview_20260927_a0v111.dump`：`pg_dump` 退出 0，3,917,396 字节，SHA256 `243b627ca88bdbd601a76fc2513f05c2f39d2e7ae5646180c0a68730a49ab3fd`，`pg_restore --list` 退出 0、TOC 5551 行。独立 test-only `aos_bg00z_cutover_20260929` 全库恢复和 `a0v_111→a0v_112` 退出 0，源/克隆 575 表、12 序列、1096 索引及非商城源安装/制品摘要一致；迁移后 579 表、四新表全空、RLS/FORCE 开启。当前库零连接升级到 `a0v_112` 退出 0，签名 Receipt 预检 GREEN，并短暂重启 API/Web。
- **权限漂移发现**：当前四表回读 `aos_runtime=arwd`，原克隆 `aos_runtime=r`，故首轮不判 GREEN。只读查到当前 `pg_default_acl` 为 `aos_app/public/table → aos_runtime=arwd`；首轮克隆使用 `pg_restore --no-acl`，漏掉默认 ACL。再次停 API/Web，三端口关闭。当前四表仍空，未发生 Eval Run。
- 第二份停机库 dump `/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260929-bg00z-acl-5vUCKo/aos_current_preview_20260927_a0v112.dump`：`pg_dump` 退出 0，3,942,521 字节，SHA256 `b6746581be11ea6889f4b5bcfa6ae715cb5e10d52294db0e40e513d5e0067914`，`pg_restore --list` 退出 0、TOC 5594 行。在另一全新 test-only 库 `aos_bg00z_acl_20260929` **保留 ACL** 完整恢复，退出 0、日志 0 字节；先回读 `a0v_112`、四表 `aos_runtime=arwd`、原 default ACL `arwd`，精确复现权限异常。两份备份与既有所有库/卷均保留。

## RED → 修复 → 最新栈回读

- 新 ACL 克隆测试先 RED：`test_acl_faithful_clone_is_least_privilege` 退出 1；只新增 `a0v_113_eval_execution_acl_fix.py`，四表逐张 `REVOKE ALL FROM PUBLIC,aos_runtime; GRANT SELECT TO aos_runtime`，不修改已执行的 `a0v_112`，不全局改旧默认 ACL。克隆升级 `a0v_112→a0v_113` 退出 0，ACL 专项 `2 passed`。
- 当前预览版本门测试 `a0v_112→a0v_113` 先 RED 退出 1，然后只改 `scripts/a0v_current_preview_http.py` 一个常量，聚焦专项 `5 passed`；编译和 diff 检查退出 0。零连接当前库升级 `a0v_112→a0v_113` 退出 0，四表 `SELECT=true`、`INSERT/UPDATE/DELETE=false`、行数全 0，签名安装预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、版本 `a0v_113`。
- 最新 `m1@d95d4043` API session `22881` 启动，日志明确 `migrationMode=disabled`、`runtimeHost=0`、worker disabled；Web LaunchAgent 重新 bootstrap，`8080 /v1/health`、`/v1/ready`、`/openapi.json` 均 HTTP 200；8434 八工作台路径及 `/aip/skill-publish`、`/aip/agent-catalog` 十路径 HTTP 200；18181 无监听（`lsof` 退出 1）。PG Docker inspect 挂载仍为 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`。
- 当前库 `BEGIN READ ONLY`：`a0v_113`；四表 RLS/FORCE 均 true、运行角色 `SELECT=true` 和 INSERT/UPDATE/DELETE=false，四表及 Runtime Binding/Host Assignment/Eval Run 均 0。`bundle_installation` 1、`asset_bundle_version` 4、`asset_bundle_artifact` 209、`aip_skill_template_revision` 37 的逐行摘要与迁移前完全相同。BG-00y schema、BG-00z ACL、BG-00w 验签/Runner、当前预览门累计 `32 passed`，退出 0。

## 结论与剩余风险

当前卷的备份、两次独立全库恢复、ACL 漂移复现与修复、当前迁移、最新代码 PG/API/Web 重启均有上述命令/退出码和读回证据。此前 `--no-acl` 克隆只证明数据恢复，不能证明权限等价；第二克隆补足了这一点。默认 ACL 全局 `arwd` 仍是独立技术债，本波仅对四张 Eval 表撤权；未来迁移必须先做 ACL-faithful 克隆/显式撤权审查。

本会话没有 `browser-pilot` 可用工具，未做截图或八页面渲染/交互验收；HTTP 200 仅证明可达。正式 G2 内容 producer/Owner、独立签发/批准、真实 S3 回环、同事务 Receipt 消费、自然首条经营闭环、卸载重装与八工作台业务结果仍未证明。Host/worker/Provider 不得开启；旧 12 Run、商城源、dev-org 写入和 230 L0 均未触碰。
