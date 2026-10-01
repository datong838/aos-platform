# BG00GX｜隔离真实来源克隆 130→132 verification

基线 `m1@27d57c7e` / AOS-001078。Task `W5CB4-BG00GX-CLONE-131-132-20261002`，计划 `bg00gx-clone-131-132-plan-20261002.md`。本波无产品代码变更、无当前实例迁移或重启。

| 核查 | 命令或证据 | 结果 |
|---|---|---|
| m1/代码头 | `git rev-parse HEAD`; `cd services/aos-api && .venv/bin/python -m alembic heads` | `27d57c7e26265f0e1804f4c13c1252924b4573df`，`a0v_132`；exit0 |
| 卷隔离 | `docker --context colima-aos-extension inspect aos-a0v-recovery-pg`; `docker --context colima-aos-a0v-test-only inspect aos-bg00dl-isolated-pg` | 当前卷 `aos-a0v-recovery-pg-data`，目标卷 `aos-bg00dl-isolated-pg-data`；18440 为隔离库，exit0 |
| 原备份 | `shasum -a 256 aos-recovery/.aos-current-backup-20261001-bg00gu/current.dump` | `e27b886f0a8fc94c6bc259b2a29250316d23f1e4d4567d3ea2589629d5d298f7`，与 BG00GU 一致；exit0 |
| RED | `services/aos-api/.venv/bin/python aos-recovery/.aos-current-backup-20261001-bg00gu/upgrade132.py` 的执行前断言 | 隔离库 `a0v_130`、subject receipt 表不存在，真库 `a0v_118`、隔离库无其他客户端；`RED_CLONE_130_SUBJECT_TABLE_ABSENT_SOURCE_118` |
| 逐步迁移 | 同上一次性脚本，SHA256 `18506c612c9ad85238efffac51674621d06725557e66ae97fb29fbc53fbfde4e`；`py_compile` exit0 | 原 Alembic `130→131→132` 两步事务/独立版本回读 exit0；唯一 intent/done 留在私有目录，脚本拒绝重跑 |
| 后验 | `docker ... psql -U aos_app -d aos_bg00gu_current_20261001 -Atc ...` | clone132；两张新表均0行；case proof有3个FK、2个非内部触发器；真库仍118；exit0 |
| 原数据与 ACL | 只读 Python 对 `upgraded.json` 中587张旧表计数和16个非版本控制表行hash复核；`has_table_privilege` | 587张旧表计数不变，16个hash一致；两张新表 `aos_runtime` 仅 SELECT，无INSERT/UPDATE/DELETE；exit0 |
| 专项回归 | `services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_eval_subject_persistence_pg.py services/aos-api/tests/aip/test_aip_eval_subject_report_sidecar_pg.py` | 9 passed、7 warnings，exit0 |

私有完成记录 `upgrade132-verified.json` SHA256 `70c5093309e94eee8adb98eb19b230d018e3d61e6fd36602da7bce302626a1e6`，结果 `ISOLATED_REAL_SOURCE_CLONE_130_TO_132_GREEN`。代码与方案一致：只对指定隔离库 DDL，失败保留现场，未 stamp/降级/覆盖原备份。没有浏览器入口改变，浏览器验收不适用。

**结论边界**：这是 10 月 1 日真库一致备份所生隔离克隆的增量迁移演练，不是 10 月 2 日当日新备份、当前真库切换或最新 API/Web 完整重启。现有 API/Web 进程仍是旧启动时间；当日重启验收尚未完成。正式 identity、subject writer、自然 Eval/首链与八工作台业务仍待证。

**下一波**：重启提醒送达后先确认最新 HEAD/数据卷/迁移差及独立当日备份，做全库新克隆到届时代码头；缺合法当前库切换前置则明确安全禁入，同时推进已登记的原生成 Owner→EvalRun/Report writer→Stage consumer 代码路径。当前真库保持只读，Host/worker/Provider 关闭。
