# W5CB4 BG00bx｜当前权威卷 a0v117 独立安全切换方案

## 输入与范围

依据 BG00bw 已审代码 `m1@49ffc96e`、231/231-3/231-5、当前恢复规范。唯一目标为 `aos-a0v-recovery-pg-data` 中 `aos_current_preview_20260927@a0v_116`。仅修改 `scripts/a0v_current_preview_http.py` 的预期 schema head 116→117，及其精确断言测试 `services/aos-api/tests/extension_runtime/test_a0v_current_preview_http.py`；当前库仅执行精确 `a0v_116→a0v_117`。保留 a0v116 active DB 禁入、签名安装和历史控制行；Host/worker/Provider 继续关闭。

## 顺序和中止门

1. 读 m1 工作树/当前卷/PG identity/迁移/安装/端口，确认独立 clone test GREEN。停 Web LaunchAgent 与 API，确认8080/8434/18181无监听，PG 除维护连接外其它会话0。
2. 停机状态新建 mode600 `pg_dump -Fc`，记录 SHA256、字节、TOC；全库恢复至全新 `aos_bg00bx_cutover_testonly_20260930`，`--no-owner --single-transaction --exit-on-error`。逐项比较安装五控制表 count/row digest 与原库；克隆迁移117，精确读回元数据、触发器、runtime固定 ID 写拒绝、普通对象可写回滚和 active 拒绝。
3. 再读零执行窗口、当前库仍116、卷身份与备份哈希。任一漂移停止，保留116且不启动最新代码。全绿后对明确库名用 Alembic 程序接口在单事务切117；读回版本/元数据/active门与五控制表 digest。
4. 更新脚本预期头，重启同一 PG 容器、签名 preflight、API与Web；读回18435/8080/8434与18181关闭、health/ready/OpenAPI、八工作台与 AIP 页面、当前正租户安装/绑定及 dev-org 隔离、网络提案/批准/active 0。专项与相邻回归后精确提交、verification、01/06/D-waves。禁止以HTTP200当首链完成。

## 恢复

迁移事务失败不提交，维持当前116并重启旧兼容脚本；若迁移已提交但服务失败，保留停机备份和克隆，不自动 downgrade 或重放业务，先只读定位再最小修复。任何外部未知结果只读对账，不重发。当前真实库写入限本独立迁移，没有产品配置、账号、提案或策略写入。
