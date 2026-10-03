# E17-s3o-w-an｜恢复克隆 Reader ACL 与 NOINHERIT 验证

依据同前缀方案与已验证的 `a0v_135` 全备隔离恢复；变更仅限 Reader 身份预检的一项缺失角色属性和对应测试。当前权威库仍只读，Host/worker/Provider 关闭。

| 门 | 命令与结果 |
| --- | --- |
| RED | `AOS_DOTENV_DISABLED=1 AOS_TEST_USE_SHARED_DATABASE=0 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_e17_s3oo_capability_reader_pg.py::test_reader_rejects_inherit_role` → `Failed: DID NOT RAISE ReadinessReaderConnectionBlocked`，exit1。原 `_require_identity` 未检查 `rolinherit`。 |
| 最小修复 | `aip_binding_readiness_reader_connection.py` 在角色预检中读取并拒绝 `rolinherit`；未变更白名单、授权、RLS 或连接身份；`test_e17_s3oo_capability_reader_pg.py` 增一条 `ALTER ROLE ... INHERIT` 负例。 |
| 专项/相邻 | Reader+issuer 13 passed、exit0；Binding readiness、预算、Reader、EvidenceBundle 撤销四文件 43 passed、exit0，7项既有 warning。`py_compile` 与目标 `git diff --check` exit0。 |
| 当前全备克隆 | `AOS_DOTENV_DISABLED=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python services/aos-api/tests/aip/e17_s3owan_restored_reader_probe.py` exit0：无角色 RED；独立非 owner/NOINHERIT 登录、全局目录10条、同租户 frozen exact 正向、错租户负向、exact revoke 负向；撤 revoke 表 SELECT、额外 SELECT、INSERT 与改成 INHERIT 均失败封闭。随机口令仅在内存及0700/0600临时 passfile；最终角色数/policy数均0。该克隆留有3对明确 test-only 的 bundle/revoke 记录，未删除历史库。 |
| 源与服务 | 当前源只读 SQL `a0v_135`、正式 Reader 角色0、EvidenceBundle/revoke 0/0、Installation1、RegistryReceipt6，exit0；测试克隆 role/policy 0/0，exit0；API `/v1/health`、`/v1/ready`、OpenAPI 与 Web `/aip/skill-publish` 都200。误探 `/health` 得404是路径不匹配，正确项目端点为 `/v1/health`。 |

结论：当前全备可恢复，独立 Reader 在恢复克隆的最小表 ACL/RLS 正反链成立，且修补了潜在的 INHERIT 身份旁路。当前正式库仍没有 Reader 角色或私有连接身份；这份证据不授权当前库切换、Host 启动、八类配置或自然首链。下一独立维护波需新一致备份/再次恢复、正式角色凭据来源和零执行窗口，再考虑当前卷受控切换。
