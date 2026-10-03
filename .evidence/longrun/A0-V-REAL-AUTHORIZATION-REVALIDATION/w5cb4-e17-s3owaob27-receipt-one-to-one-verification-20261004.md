# E17-s3o-w-ao-b27｜同版本 Capability Receipt 一一配对隔离验证

## 方案、RED、最小实现

- 方案先提交 `m1@bad6d7d2`，仅在 `services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py` 的 disposable full-schema PG 试验；现有 `aip6_002` 仅唯一约束 `(org,project,operation,idempotency_key)`，b24/b26 双向守卫用 EXISTS，未约束不同键的同版本 Receipt 数。
- 新增独立 issuer 一次合法 evaluate 行写后发两张不同键、同 `(tenant,binding,version,operation)` Receipt 的负例。目标单项第一次 exit1，`1 failed`，`Failed: DID NOT RAISE InsufficientPrivilege`；与计划的缺口一致。
- 最小修正只在 test-only Receipt 与 Binding deferred guard 中要求当前事务对同租户、同 Binding、同版本 `capability_binding.%` Receipt 计数精确1，保留原 exact operation/marker/xmin 检验；普通 Agent/Skill/Run/Handoff 不进此计数。未增加生产迁移、未修改正式工厂或当前 API。

## 回归与复审

- 五文件相邻组 `AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py tests/aip/test_e17_s3owaob12_tool_receipt_identity_pg.py tests/aip/test_e17_s3ol_capability_issuer_pg.py tests/aip/test_aip6_003_exact_instance.py tests/aip/test_aip6_capability_run_handoff.py -k 'not downgrade'` exit0，`14 passed, 1 deselected, 1 xfailed`。xfailed 为生产共享 Receipt 无配对写既有缺口；deselected 为当前135不可降级的旧测试。`py_compile`/`git diff --check` exit0。
- 原库 `BEGIN READ ONLY` 后读 `a0v_135`/Binding0/Receipt6，未写。测试文件的最终 Receipt7/Binding1 断言通过，新增负例没有持久化额外行。当前签名预览写503、Host/worker/Provider关。
- 本波仅防同版本多 Receipt；test-only `SET ROLE`/身份不是正式独立凭据。正式受控 operation 来源、完整非法列矩阵、历史 Binding/事务回滚和独立 issuer/RLS/ACL 仍待下一波，不能把隔离 GREEN 说成 `a0v_136`、当前安装可运行或自然首链完成。
