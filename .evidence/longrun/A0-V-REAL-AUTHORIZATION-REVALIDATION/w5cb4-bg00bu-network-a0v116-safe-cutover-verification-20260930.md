# W5CB4 BG-00bu｜a0v116 网络 active 数据库写门与安全切换 verification

方案 m1 `2decdcbb`，最小迁移/代码 `2eac86f6`，相邻历史行夹具修复 `57e0da18`。依据 231/231-4/231-5、41 网络方案、BG-00bo/bt。本波只给 NetworkPolicy revision 增加 `BEFORE INSERT` active 拒绝门，未接正式批准消费、未读商城源或旧 12 Run、未启 Host/worker/Provider。

| 门 | 本次命令与证据（均退出0，特别注明者除外） |
|---|---|
| RED/最小代码 | `test_a0v_current_preview_http.py` 预期116先 `1 failed,2 passed`、退出1；迁移 `a0v_116_network_active_insert_gate.py` 线性115→116，仅对 active 抛 `NETWORK_ACTIVATION_CONSUMPTION_REQUIRED/23514`，draft不变；最新代码预检头改116。静态/邻接 4 passed、compileall/diff check退出0。|
| 第一隔离克隆 | 旧当前115 dump SHA256 `75d7fa0b…cf51c0` 全库恢复到 `aos_bg00bu_network_gate_testonly_20260930`，单步迁移116退出0；以 `aos_runtime` 直写 active 得23514，draft 事务内成功后 rollback，最终目标行0，输出 `bg00bu_clone_active_block_draft_allow_green`。|
| 零执行窗口 | `launchctl bootout` Web、API PID12713 SIGINT，8080/8434/18181 均无监听；当前库其他会话0、源115、网络 head/revision0。容器卷回读 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`，未启动 Host。|
| 新可恢复备份 | 停机后 `pg_dump -Fc` 到 `/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260930-bg00bu-PjWfUj/aos_current_preview_20260927_a0v115.dump`；3,952,285 bytes、0600、SHA256 `17a92e57e873365da7258f8304d83bf58bf7cdff72667a81abd527900fca77ac`，`pg_restore -l` TOC5609。保留先前备份，不删除任何库/卷/备份。|
| 第二全库克隆 | 从新 dump `pg_restore --no-owner --single-transaction --exit-on-error` 到 `aos_bg00bu_cutover_testonly_20260930`，源/克隆115；五控制表 count+行 hash 合计一致：installation1/revision3/bundle4/version4/binding0。克隆115→116退出0，runtime active 拒23514、draft可写并 rollback，策略三表0；升级后控制摘要仍与源一致。|
| 当前单步迁移 | 再核8080/8434/18181 无监听、其他会话0、卷/备份 SHA256、源115/无 active trigger；程序化 Alembic 只对 `aos_current_preview_20260927` 执行115→116，退出0。只读查当前与克隆116、enabled active trigger各1、网络 head/revision/receipt各0、五控制表摘要完全一致。当前库没有测试数据写入。|
| 最新栈复验 | `docker restart aos-a0v-recovery-pg` 后卷仍为 `aos-a0v-recovery-pg-data`；签名 Receipt 预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、approved安装1/published4/binding0/version116。API PID15420 启动回读 `migrationMode=disabled,runtimeHost=0,workersEnabled=0`，Web LaunchAgent PID15437；18435/8080/8434 监听，18181无。API `/v1/health`、`/v1/ready`、`/openapi.json` 200；八 `/workshop/*`、`/aip/skill-publish`、`/aip/agent-catalog` HTTP200。|
| 租户与回归 | 当前库只读 `org-org/dev-project` 安装1，`dev-org/dev-project` 安装0，正租户绑定/网络 ObjectType/ActionType/Proposal/ApprovalEvent/Network row均0，enabled触发器1。旧网络历史 active 测试夹具最初被正确拦下（1 failed/14 passed）；限定 pytest 一次性库、事务内 disable/seed/enable 后相邻19 passed。累计回归见下方。|

累计八组 AIP Action/Network 与启动测试 **48 passed，退出0**，`git diff --check`/compileall 退出0。相邻夹具的触发器关闭只在 `aos_test_*_ti4_test` 一次性库、核触发器存在并同事务恢复；异常 rollback 恢复，不涉及当前真实库。迁移的 active 门后续只能在独立原子消费方案与安全迁移中改变。当前没有正式 NetworkPolicy 元数据/真实 checker、一次性消费、八配置/Host/自然首链；页面 HTTP200 只证明路由可达。browser-pilot 当前不可用，无截图交互验收。BG-00bv 从正式元数据来源和消费协议独立方案推进。
