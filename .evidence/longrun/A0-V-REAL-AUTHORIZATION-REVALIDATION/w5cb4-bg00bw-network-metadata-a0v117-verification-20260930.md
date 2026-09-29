# W5CB4 BG-00bw｜a0v117 正式网络元数据代码与克隆验证

## 范围

依 BG00bw 文件级方案，只新增 `a0v_117_network_formal_metadata.py` 与显式 clone 测试。当前权威库仍 `a0v_116`，API/Web 未重启；Runtime Host/worker/Provider 关闭。迁移只注册固定全局元数据并保护 ObjectType ID，不产生真实 checker、Proposal、ApprovalEvent 或 active 策略。用户另有浏览器插件/lock 未提交改动，未触碰。

## 新鲜证据

- 当前 `m1@9b5d34a3`，`docker ... psql ... alembic_version` → `a0v_116`；当前固定 ObjectType/ActionType 均0。`docker ps` PG运行、`lsof` 18435/8080/8434 LISTEN，18181无。
- 一致 `pg_dump -Fc` 退出0：`/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260930-bg00bw-testonly-qYV9j3/aos_current_preview_20260927_a0v116.dump`，3,953,550 bytes，已 chmod600；SHA256 `df89d1a16738478ad247200425f170454dc3cba82dd915860d6c3324456055da`，容器 `pg_restore -l` 退出0。仅用于 test-only clone；当前切换另需停机一致备份。
- 全库恢复至 `aos_bg00bw_metadata_testonly_20260930`，`pg_restore --no-owner --single-transaction --exit-on-error` 退出0。显式 clone 测试 RED：`a0v_116` 与期望117不符，1 failed；显式迁移 `a0v_116→a0v_117` 退出0；GREEN 1 passed。
- 测试核对 Producer `_OBJECT/_ACTION` 所有字段、runtime 固定 ObjectType INSERT/UPDATE/DELETE 与 ActionType UPDATE均42501、普通 ObjectType INSERT 可在同事务回滚、a0v116 active 触发器仍启用。
- 五张安装控制表当前与 clone count/row digest 相等：`asset_bundle 4/1695185680822825726`、`asset_bundle_version 4/-790554283954760494`、`bundle_installation 1/4398438098674159491`、`bundle_installation_revision 3/1650834216456423558`、`extension_runtime_binding 0/0`。
- 相邻 `test_aip_network_policy_action_producer.py`, `test_aip_network_policy_store.py`, `test_aip_network_policy_action_producer_pg.py` → 14 passed/1 skipped（clone 专项另跑）；`compileall` 与 `git diff --check` 退出0。未用 mock 代替当前正式正向。

## 复审与未完成

与 231/231-5/41 及 Producer 合同一致：元数据可由迁移审计，普通对象编辑保留，固定 ID由表 owner保护；a0v115 ActionType 门与 a0v116 active 禁入不变。真实第二 checker/OIDC 身份仍缺，当前不许启 Host 或宣称首链。下波独立 BG00bx：新停机一致备份、SHA/TOC、第二全库克隆恢复和完整表对账、零执行窗口后切当前 a0v117，更新签名预检预期头并全面重启；失败回到 a0v116，禁止强行启动。
