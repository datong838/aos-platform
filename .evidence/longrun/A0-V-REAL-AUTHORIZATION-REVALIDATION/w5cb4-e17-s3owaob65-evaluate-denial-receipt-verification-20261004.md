# b65 verification：普通 evaluate 明确禁入，Receipt operation 仍 RED

- Task：`A0V-W5CB4-E17-S3OWAOB65-20261004`；方案：同目录 `w5cb4-e17-s3owaob65-evaluate-denial-receipt-plan-20261004.md`。
- RED：原普通 lifecycle issuer `evaluate` 先经 Reader 预计算，再在 Binding UPDATE 因列权限失败，映射 `AipAgentRegistryPersistenceError`。新入口测试修改后首次运行 exit1：期待 Conflict，实际 PersistenceError。共享 Receipt 伪造测试 strict xfail。
- 最小代码：原 Service `evaluate` 在 `_validate_command` 后、任何 `get`、Reader 或连接调用前，识别原生产 `RegistryIssuerConnectionFactory(command_family="capability_lifecycle")`，抛 `AIP_BINDING_EVALUATOR_REQUIRED` Conflict；Router 既有映射返回409。默认服务及 create/update 未变。
- 专项及相邻：`AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings --show-capture=no tests/aip/test_e17_s3oo_capability_reader_pg.py tests/aip/test_e17_s3ol_capability_issuer_pg.py tests/aip/test_aip_binding_api.py tests/aip/test_e17_s3owaob20_current_binding_private_admission.py`，exit0，`35 passed, 1 xfailed`；普通 issuer evaluate 的 Reader 观察列表为空，Binding version/Receipt 未变，revoke/create 正向仍通过。`py_compile` 与 `git diff --check` exit0。
- 回执风险证明：同一隔离 PG `--runxfail` 仅运行 `test_ordinary_capability_issuer_cannot_forge_evaluate_receipt`，exit1，`DID NOT RAISE InsufficientPrivilege`。普通 issuer 可独立插入 `capability_binding.evaluate` 伪回执；此 RED 未解决，不能据此宣称可信 available 或正式评估闭环。
- 后续：正式 Receipt operation guard 需绑定可信 evaluator 最终事务、身份/ACL 和唯一136，覆盖错租户、错 key、重复、失败回滚及 signed Installation/Registry 锁。当前库只读，无 Host/worker/Provider、无业务副作用。
