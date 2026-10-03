# W5CB4 E17-s3o-u｜配置来源 ACL 预检验证

日期：2026-10-03，北京时间。基线 `m1@533e191a`、Authority `AOS-001206`。计划在同前缀 plan。仅在无挂载的既有 `aos-ar1c-pg` 隔离容器（127.0.0.1:18432）运行 opt-in ephemeral schema 测试；容器由 exited→running，未删除卷/库/备份。当前权威卷 `aos-a0v-recovery-pg-data` 只读。

## 当前权威来源事实

经 Docker inspect 校验容器 `aos-a0v-recovery-pg` 正在运行且 `/var/lib/postgresql/data` 挂载为上述权威卷，显式连接 `aos_current_preview_20260927`、`SET TRANSACTION READ ONLY`：`alembic_version=a0v_135`。`has_table_privilege('aos_runtime', ...)` 回读：职责计划 head/revision 的 SELECT/INSERT/UPDATE/DELETE 全 true；生产合同 Receipt SELECT/INSERT/DELETE true、UPDATE false；三表 RLS 与 FORCE RLS 均 true。FORCE RLS 只隔租户，不区分同租户正式发行者与普通运行写者。未读取商城源数据。

| 验证 | 精确命令或路径 | 结果 |
| --- | --- | --- |
| 基线 | `AOS_EXTENSION_PG_TEST=1 services/aos-api/.venv/bin/pytest -q services/aos-api/tests/extension_runtime/test_configuration_stage_preflight_pg.py --tb=short` | exit 0，17 passed |
| RED | 同文件 `-k 'source_head_insert or missing_current_source_table' --tb=short` | exit 1，3 failed/25 deselected；旧代码在来源可写及缺表时仍 `True` |
| GREEN | 上述预检文件全量 | exit 0，28 passed |
| 相邻回归 | `AOS_EXTENSION_PG_TEST=1 services/aos-api/.venv/bin/pytest -q services/aos-api/tests/extension_runtime/test_configuration_stage_preflight_pg.py services/aos-api/tests/extension_runtime/test_configuration_stage_host_selection.py services/aos-api/tests/extension_runtime/test_configuration_stage_consumer_pg.py services/aos-api/tests/extension_runtime/test_current_configuration_sources_pg.py --tb=short` | exit 0，63 passed |
| 静态/服务 | `python -m py_compile` 两改动文件；`git diff --check --` 两文件；`curl /v1/health` 与 Web `/aip/skill-publish` | 静态 exit0；API/Web HTTP200；Host/worker/Provider 未启动 |

## 一致性、风险、下一门

- 只改 Host 配置阶段启动预检和隔离测试。三张原来源表必须存在、FORCE RLS、普通运行角色可 SELECT 且无 INSERT/UPDATE/DELETE/TRUNCATE；任一漂移即不选择配置阶段消费者。原配置 Store、四源内容读取与当前真库均未改。此为安全禁入，不是八类配置已签发。
- 预检在 Host 选择时执行；启动后权限被管理员改宽的漂移尚无每次消费前复查。本波不宣称长期动态 ACL 证明，下一波需在原配置消费事务中复用只读 ACL 检查并做 TOCTOU 负例。
- 当前实例会因已有宽权限而保持配置阶段禁入。要正向启用须先有独立 Plan/Receipt 发行与合法正式身份，再做当前 ACL 迁移：新全备可恢复、克隆全链、零执行窗口；不得凭新预检通过或模拟测试启 Host。旧 RETURN、Tool issuer、六 Binding、八类当前配置和自然首链仍待完成。
