# W5CB4 P2g23：092→106 迁移无效果预检

日期：2026-09-27。方案先行 `m1@4e507b9b`。本波仅检查本地迁移文件、恢复库元数据、运行状态、备份目录与空间；未运行迁移、未备份/覆盖、未启动 API 或 worker，未读商城源或旧 Run payload。

## 已核事实

- P2g22 在 scoped `READ ONLY` 事务中确认恢复库 `aos_meta_head` 的 Alembic 为 `a0v_092`；当前代码头是 `a0v_106`。Runtime 仍 `observed=unknown`、`enabled=false`、fenced，精确 content-review dispatch 的 epoch 不匹配。当前 API/worker 启动门仍关闭。
- 本地 Alembic `history -r a0v_092:a0v_106` 是 093–106 共 14 个线性迁移，无分叉。093/094 增 Host lease/fence；095 增严格 claim；096 撤销 legacy unknown reconcile，且 `downgrade()` 明确报错；097/098 增 snapshot witness 与受控回填门；099/100 增 daily target 及其撤权/终态门；101–104 增内容任务、AgentRun、capacity/budget intent 结构；105 重建 `aip_eval_run` 和 `aip_eval_report_revision` 的 CHECK 约束，需独立评估锁与旧数据；106 增 improvement target/函数并收紧 daily/improvement 直接表写权。函数中的 `INSERT/UPDATE` 是运行时逻辑，不等同于本波已执行 DML。
- 恢复 DB 只读尺寸读回为 130,645,015 bytes；检查时 `pg_stat_activity` 只有本次读连接，`pg_locks` 只有本次查询的两个 granted AccessShareLock。这只是瞬时观测，不是未来迁移窗口保证。
- Docker inspect 确认恢复容器 `/backup` 是只读 bind mount，源声明为 `/Users/ddt/work/projects/ai_agent/.aos-recovery-20260910/backups`；容器内 `ls -la /backup` 仅 `.` 和 `..`，没有可验证的当前备份文件、大小、时间或校验清单；Mac 上该声明路径也未找到。不能声称具备回滚点。
- 检查时 Mac 数据卷可用 56 GiB（87% 已用）；容器数据卷可用 15.0G，`/backup` 所在挂载可用 17.1G。空间数值不替代备份一致性、恢复演练或锁窗口证明。

## 结论与停止门

**STOP_MIGRATION / STOP_CURRENT_API_AND_WORKERS**。没有独立校验的一致当前备份，096 不是普通 downgrade 可逆，105 有锁/旧数据验证风险；现行 Runtime 也不是可执行权威。不得在恢复库运行 `alembic upgrade`、开启 8080/18181 或自然 worker。

真实迁移另波须先证：当前一致备份与独立恢复校验；隔离克隆逐版本 093–106 演练和 096/105 停止/恢复策略；API/Host/worker 零执行与可控锁窗口；迁移后独立只读版本/ACL/RLS/安装/Host 读回。不能用空目录或一次性测试库代替上述证明。下一波优先推进不依赖真实库迁移的首链代码/验收缺口，迁移准备列为独立并行只读任务，避免主线死磕。

浏览器验收不适用：本波没有页面或服务变更，且安全门禁止启动当前 API。
