# W5CB4 E17-s3o-u｜配置阶段原来源 ACL 预检

日期：2026-10-03。编码前复习 `231-3/5/9`、栖月汇产品方案、E17-s3o-s/t、原 `configuration_stage_preflight.py`、`configuration_stage_consumer.py`、`aip_runtime_configuration_sources.py`。当前权威库 `aos_current_preview_20260927@a0v_135` 只读核：`aos_runtime` 对 `aip_responsibility_plan_head/revision` 有 SELECT/INSERT/UPDATE/DELETE，对 `aip_production_contract_receipt` 有 SELECT/INSERT/DELETE；三表均 FORCE RLS。此角色可以在租户内造 Plan 和回执，故原四源读者只验行/哈希不足以证明专用发行。当前 Host/worker/Provider 关闭。

## 文件级步骤

1. RED：`services/aos-api/tests/extension_runtime/test_configuration_stage_preflight_pg.py` 隔离 schema 增三张只含 ACL 的源表，默认 FORCE RLS、运行角色仅 SELECT；在已有预检正向之后分别给普通运行角色加来源表 INSERT/UPDATE/DELETE，断言拒绝。旧代码预期误放行，记录失败。
2. 最小实现：仅改 `services/aos-api/aos_api/extension_runtime/configuration_stage_preflight.py`。延续现有 idle、非 owner、FORCE RLS、暂存权限/trigger 检查；再要求三张来源表均存在、FORCE RLS、`aos_runtime` 仅可读，不可 INSERT/UPDATE/DELETE/TRUNCATE。不得改四源实际内容读者、配置提交或当前库 ACL。
3. 聚焦/相邻回归：预检 PG、Host selector、配置消费者与来源读者；`py_compile`/`git diff --check`。代码只影响显式启用的 Host 配置阶段准入；当前库仍失败关闭，不能称正式配置可用。
4. 复审：此检查只阻止宽权限运行角色被当成可信发行源，不能代替 Plan 专用发行身份、原事务冻结 Receipt/模板信任链、API 外部 OIDC。正式 ACL 迁移需新全备、克隆全链和零执行窗口，独立下一波。

范围外：当前真库写入、Host/worker/Provider 开启、旧 12 Run、商城源、230 L0、测试身份提升为正式身份。下一波落 Tool/Plan 专用 issuer 与旧 API 写权收窄的隔离链。
