# b64 文件级方案：Capability 生命周期 issuer 精确列级预检

## 依据和风险

- b63 disposable PG：仅 `UPDATE(status,health,observed_at,version,updated_at)` 已可拒绝普通 issuer 直写 readiness，但现有 `RegistryIssuerConnectionFactory(command_family="capability_lifecycle")` 要求表级 UPDATE；b62b 证明广授权可伪造 available/Receipt。
- 231-3/BIND-1 要求当前签名与八依赖可信最终事务；本波仅收窄普通生命周期发行身份，不能宣布 evaluate/active 正向可用。当前真库 a0v_135 只读。

## 文件级实施

1. `services/aos-api/aos_api/aip_registry_issuer_connection.py`：用 `pg_attribute` 枚举所有非删除的 Binding 列，计算当前 session_user 可 UPDATE 的列集合；`capability_lifecycle` 必须精确等于五个状态列，`capability` 必须为空。任何表级 UPDATE、readiness/依赖/快照/时间窗或将来新增列的写权都使预检失败；其他 command family 保持原边界。
2. `services/aos-api/tests/aip/test_e17_s3oo_capability_reader_pg.py`：b63 strict xfail 转 GREEN；新增表级 UPDATE、额外 readiness 列、缺必需列、DELETE 和错租户拒绝。旧 `test_original_capability_evaluate_uses_explicit_reader_and_issuer_cas` 的广授权正向必须更正为**旧 evaluate 失败关闭**，保留 Reader 的独立 read-only 测试；不因旧用例需要而留下伪造通路。
3. 运行专项/相邻 issuer/API 测试及静态检查；检查既有 create/status 语义无倒退。若碰到正式 Receipt operation guard/受限 evaluate 缺口，仅局部记录并留唯一136，不借 test-only 角色放通当前实例。

## 回滚与边界

- 代码只改身份预检，无迁移和正式 GRANT；正式凭证尚未签发，当前生产组合根仍默认未配置私有 issuer。回滚为撤销此未部署 preflight 切片；不触当前库数据。
- 受限可信 evaluator、同事务八依赖、Installation/Registry 锁、Binding CAS/唯一 Receipt、安装换代及当前库新备份/全恢复/零执行窗口是后续门；Host/worker/Provider继续关。
