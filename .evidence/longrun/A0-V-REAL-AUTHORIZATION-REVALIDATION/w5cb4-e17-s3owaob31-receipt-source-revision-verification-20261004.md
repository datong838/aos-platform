# E17-s3o-w-ao-b31｜当前 Installation 对账与 Capability create Receipt 来源版本

## 当前实例只读对账

- `aos_current_preview_20260927@a0v_135` 的原 Installation 单条：rev1 draft、rev2 submitted、rev3 approved，`current_revision=3`、`active_revision=NULL`、`etag=3`；唯一 approved 决策对 rev2 的同 lock，当前 `extension_runtime_binding` 0。Catalog 10条 published 均指 Growth1.11.0，配置 bundle root 中 Growth 也仅1.11.0。`current_installation_release_evidence.py` 只读视图允许 approved 但只输出 `EVIDENCE_ONLY_NO_START`；runtime image evidence 强制 active/current一致。以上不是缺失的 Growth1.13 正式发布、runtime-apply/verify 或自然首链。

## 方案、RED、最小实现

- 复习 231-2/231-3/231-4、BIND-1 与原 Service 后，文件级方案 `m1@098fb196` 先提交。原 `AipCapabilityBindingService.create` 在同一事务检查 Catalog exact id/revision/hash/published，却由共享 `_insert_receipt` 写 `resource_ref.revision=None`，result revision 已精确。
- 在 `services/aos-api/tests/aip/test_e17_s3ol_capability_issuer_pg.py` 的真实独立非 owner issuer create/replay/租户隔离用例先加来源 revision 断言。目标单项 exit1，`AssertionError: assert None == '1'`。
- 最小修改 `services/aos-api/aos_api/aip_agent_registry_store.py`：共享 `_insert_receipt` 增可选 `source_revision=None`；`services/aos-api/aos_api/aip_capability_binding_service.py` 仅 create 传原 `binding.capability.revision`。不改变其他 Agent/Skill/Run/Handoff 或 Capability update/evaluate 的默认来源形状，不加迁移/DDL。测试同时核对象、幂等重放及 DB 持久回读中的来源 revision。

## 回归、复审与限制

- 目标单项修复后 `1 passed, 4 deselected`；六文件相邻 `AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings tests/aip/test_e17_s3ol_capability_issuer_pg.py tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py tests/aip/test_e17_s3owaob12_tool_receipt_identity_pg.py tests/aip/test_aip6_003_exact_instance.py tests/aip/test_aip6_capability_run_handoff.py tests/aip/test_aip_binding_readiness_service.py -k 'not downgrade'` exit0，`33 passed, 1 deselected, 1 xfailed`；xfailed 是正式共享 Receipt operation门既有缺口，deselected 为135禁降级旧测试。三文件 `py_compile`、`git diff --check` exit0。`_insert_receipt` 其他调用仍使用默认 None。
- 当前权威库 `BEGIN READ ONLY` 后仍135/Binding0/Receipt6，无真实写；Host/worker/Provider关、当前 Capability 写503。此波可审计 Catalog source revision，但 `ResourceRef` 尚不带 contentHash/签名 Installation generation；Catalog 版本不等于 bundle 版本或 active 安装。当前运行 API 尚未因本波代码变化重启；下一次最新栈重启需重核备份/卷/签名/身份，再做健康和页面验收。正式 OIDC/issuer、Growth1.13 release、八配置、六 Binding、Owner/首链仍 pending。
