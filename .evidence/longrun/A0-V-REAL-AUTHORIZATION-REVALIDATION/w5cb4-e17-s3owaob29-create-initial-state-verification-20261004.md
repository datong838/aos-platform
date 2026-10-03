# E17-s3o-w-ao-b29｜Capability CREATE 初态隔离 RED

## 方案与 RED

- 231-4/BIND-1、原 `AipCapabilityBindingService.create` 与 `aip6_001/004` 复习后，先提交文件级方案 `m1@4f10fdce`。原 Service 查询精确发布的 Capability id/revision/hash 后，INSERT Binding 初态 provisioning/unknown/version1，再写同事务 Receipt。`aip6_001` 表级只限制枚举及 version>=1，b24-b28 test-only marker 将所有 INSERT 默认归类 create。
- 只改 `services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py` disposable full-schema DB test-only 探针。新独立 issuer 负例：INSERT `status=active,version=1` 或 `status=provisioning,version=2` 并配相同结果版本的 create Receipt。目标单项原 exit1，`1 failed`，`Failed: DID NOT RAISE InsufficientPrivilege`。

## 最小修复与回归

- 仅 test-only BEFORE marker INSERT 分支要求 `status=provisioning`、`health=unknown`、`version=1`，`observed_at/last_evaluated_at/dependency_snapshot_hash/readiness_expires_at` NULL，`operational_readiness=unknown`；否则42501。原合法 test-only CREATE 保持。未把 `capability_ref='{}'` 测试探针称为真实已发布来源。
- 五文件相邻 `AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py tests/aip/test_e17_s3owaob12_tool_receipt_identity_pg.py tests/aip/test_e17_s3ol_capability_issuer_pg.py tests/aip/test_aip6_003_exact_instance.py tests/aip/test_aip6_capability_run_handoff.py -k 'not downgrade'` exit0，`14 passed, 1 deselected, 1 xfailed`。xfailed 是正式共享 Receipt 无配对既有缺口；deselected 是135禁止降级旧测试。`py_compile`/`git diff --check` exit0。
- 当前权威库 `BEGIN READ ONLY` 后读135/Binding0/Receipt6。未加 `a0v_136`、未改正式 API/工厂、未重启；当前 Capability 写503、Host/worker/Provider关。

## 方案/代码复审与下一门

CREATE 初态约束解决活跃/高版本假创建，但未证明 Capability 真实已发布或签名来源。原生产 Service 有发布查询，直连 issuer 绕过仍需数据库受控命令来源与精确权限合同；test-only helper 用空 JSONB 仅测守卫。下一波应在隔离库构造真实 published revision，RED 未发布/错 hash/跨租户来源，并明确 issuer 能否直写、历史行迁移与正式凭据；缺正式来源则当前写仍失败关闭。原库只读、首链 pending，不 push。
