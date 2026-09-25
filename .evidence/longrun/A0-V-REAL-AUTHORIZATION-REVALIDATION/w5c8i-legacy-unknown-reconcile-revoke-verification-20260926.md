# W5c8i｜旧 unknown 对账旁路撤权验证（隔离环境）

## 判定

本波**代码与隔离 PG 测试通过，真实运行/closure 未授权**。按先行方案 `f5e93e69`、收敛修订 `8b3f6203`、`f067e9c6`、`82419ee7`、`6f941395`，只封闭旧的无 Host/源组校验入口；新的同事务受控正向对账尚未实现。真实 `aos-extension` Colima profile 停止，真实库未迁移至 `a0v_096`，8080 未重启；因此代码提交不等于生产撤权生效。

## 第 1/9—9/9 步

1. 复习 W5c8h 审计、`a0v_050/093/094/095`、原 Store/Worker、m1 与 AOS-000670；真实组合门保持 `FROZEN_REAL_CLOSURE_GATE_COMPOSITION / DATABASE_CONTAINER_UNAVAILABLE`，重启后的 12 Run 状态未知。
2. 文件级方案先提交并三次收敛：本波仅做旧权限 cutover 与直接调用冻结；历史 PG 测试预期和隔离库 DSN 修复分别先写方案，不扩张真实授权。
3. 新建从未承载真实 A0-V 的 `aos-a0v-test-only` Colima profile（2 CPU/2 GiB/15 GiB）、`--restart=no` PostgreSQL 16 容器；default/aos-extension profile 未启动。只在此 profile 的 disposable `aos_test_*` 库跑迁移到 head 和测试；为镜像拉取只调整该新 VM 的 DNS/Docker proxy，为 fixture 修正该 VM 时钟，未改真实 VM。迁移前撤权专项 RED，迁移后 GREEN。
4. `a0v_096` 撤 PUBLIC、runtime、directory、maintainer 对旧 `reconcile_completed_a0v_050` 的 EXECUTE，保留正常 `complete_a0v_050`。Worker 遗留显式 `reconcile=True` 在 route/Coordinator/Store 之前返回 unknown；默认 claimed 路径不变。历史 PG unknown 成功预期先 RED，再改为断言旧函数拒绝、Delivery 保持 unknown、完成引用空、零二次 source；正常 complete 与 replay 原断言保留。路由 PG 两项初次因 `conn.info.dsn` 丢失密码报 `fe_sendauth`，只修测试 DSN 并检查库名一致，未降低 PG 认证。
5. 集成专项 `test_analysis_snapshot_coordinator_pg.py -k claim_route_is_the_only_input_to_fixed_coordinator`：`2 passed, 1 deselected, 7 warnings in 354.97s`；Worker/路由/撤权/Store 短累计：`23 passed, 7 warnings in 244.55s`。早先 W5c8g 完整 PG 链 `1 passed in 175.22s`；本波变更后未重跑该独立文件，不纳入本次 GREEN。`py_compile`、`git diff --check` 通过；测试会话清理后 `aos_test_*` 数据库数为 0。
6. 浏览器只读：8080 health 曾返回 200，但本波 Vite 工作台显示“工作台目录读取失败 / tenant directory is unavailable”，组页要求确认身份，待冲刷队列 1；临时浏览器/Vite 已关闭。未执行业务点击、source 读取或写入，浏览器验收**未通过**。
7. 复审：运行角色不能再调用旧 unknown SQL，直接 Worker 分支不再先触发 Coordinator；正常 complete 未撤权。迁移 downgrade 故意 fail-closed，不会自动重授旧入口。这个隔离结果不证明真实库已迁移、不证明 Host fence/源组同事务正向对账，也不证明原 12 Run closure；过期 claimed 和上游 Store 边界仍另门。
8. 本 verification 与代码同一 m1 提交；再更新 D-waves、AOS CAS/上下文、Prime 投影并回读。`automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false` 不变；不 push。
9. 自动进入 W5c8j：先独立方案复习原 PREPARING/Occurrence/Origin/保存源组、双 Receipt 与 Host→Delivery 锁序，再做隔离 PG 下**同事务、零二次 source** 的受控 unknown 对账正/负例；无完整授权证明则 RED/STOP，不接真实 Worker、不迁移真实库、不重发旧 attempt。

230 L0 继续挂起，商城源不读，`dev-org/dev-project` 仅零 canary，未知结果不重发、不手工 `run_definition`；m1 唯一写者，不动其他分支。
