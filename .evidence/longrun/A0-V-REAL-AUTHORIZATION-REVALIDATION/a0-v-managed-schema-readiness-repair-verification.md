# A0-V Managed Schema SourceReadiness 修复验证

## 1. 结果

`A0V_MANAGED_SCHEMA_SOURCE_READINESS_REPAIR_GREEN`。

修复提交 `48c7cc28b2221e599b8efee7c3081fa7ee041918` 新增 Alembic revision `a0v_001`，将 legacy bootstrap 独占的 `meta_schedule_run` 纳入正式 managed-schema 链。未修改 SourceReadiness、Cron 或其他业务代码。

修复后首次重采的 A0-V 总结论仍为 `A0_V_BLOCKED_WITH_ACTIONABLE_GAPS`：在当时仅检查 HTTP 与集合非空的采集器口径下，blocker 从 17 降至 16，unverified 保持 1。随后 `14a1dcc8` 补齐业务语义门时为 19 个 blocker；再由 `ef18123f` 修正 A1 动态输出与 A0-V 静态前置的分类后，当前权威结果为 16 个 blocker、1 个 unverified。各数量只代表对应时点和判定口径，不能互相替代。该修复只关闭 managed-schema 缺表，不提升安装、Agent、模型、预算或真实数据源准入状态。

## 2. 修改文件

- `services/aos-api/alembic/versions/a0v_001_meta_schedule_run_managed_schema.py`
- `services/aos-api/tests/test_a0v_001_meta_schedule_run_managed_schema.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/a0-v-readiness-result.json`

## 3. 确定性验证

| 检查 | 结果 |
|---|---|
| Alembic heads | 单一 head：`a0v_001` |
| 专项迁移 + SourceReadiness 单测 | 7 passed |
| runtime grants | `SELECT/INSERT/UPDATE=true`，`DELETE=false` |
| RLS | ENABLE + FORCE；`USING` 与 `WITH CHECK` 绑定 `aos.org_id/aos.project_id` |
| 双租户读取/更新 | 运行角色只能看到并更新当前 GUC 租户 |
| 跨租户插入 | `InsufficientPrivilege`，失败关闭 |
| 非空 downgrade | `meta_schedule_run downgrade blocked: run history exists` |
| 空表 downgrade → re-upgrade | GREEN |
| 畸形 legacy 表 upgrade | `schema drift blocks managed adoption` |

独立迁移演练使用临时数据库 `a0v_verify_upgrade` 和 `a0v_verify_drift`，完成后均已删除。演练日志位于仓库外 `/Users/ddt/work/projects/ai_agent/.aos-recovery-20260910/logs/a0v-managed-schema-migration-drill.log`，SHA-256=`88c6b19ee88a5ea00cf4624be07b369d260f194d843a36cd7769fc9c8cee16bd`。

## 4. 恢复库接口复验

迁移只应用于隔离恢复克隆 `aos_meta_head`；原样历史库 `aos_meta` 未改。API 继续固定 migration、QYH Cron、Logic automation、Provider health maintenance 为 disabled/inactive。

`a0-v-readiness-result.json` 于 `2026-09-10T11:18:10.604231+00:00` 对提交 `48c7cc28b2221e599b8efee7c3081fa7ee041918` 采集，SHA-256=`00336523eb3074d17e7ea06eab0ff40b16c6f33a4428c2eea2ca6b231584f9c8`：

- `org-org/dev-project` canonical SourceReadiness：HTTP 200；
- `dev-org/dev-project` canonical SourceReadiness：HTTP 200；
- 两者均返回结构化 readiness 事实，真实缺失项包括 Pipeline、Source、Schedule、query capability exact ref 和最新成功运行；
- 缺失 Bearer 仍为 401，非法 limit 仍为 400；
- 当时版本验证器：`A0_V_EVIDENCE_VALID blockers=16 unverified=1`；当前结果与口径见 `a0-v-semantic-readiness-gates-verification.md`。

## 5. 风险与下一步

恢复数据库只来自 2026-08-05 历史备份，不能用于判断 2026-09-10 正向租户配置是否仍存在。A0-V 后续需依据当前可恢复事实补齐或重新建立安装、Workshop、AIP catalog、生产契约、模型路由/健康和预算配置，并用正向资源做 canary exact-id 反查。在这些门全部关闭前，不能进入 A1 真实 Provider 链。
