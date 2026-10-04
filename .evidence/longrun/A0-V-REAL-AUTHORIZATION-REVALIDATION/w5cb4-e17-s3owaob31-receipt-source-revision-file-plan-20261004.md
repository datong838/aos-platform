# E17-s3o-w-ao-b31｜当前安装只读对账与 Capability create Receipt 来源版本

## 上位与现时事实

- 231-2/231-3/231-4：签名制品与原 Installation 状态分离；approved 允许 runtime-apply，但只有后续 verify/active 同源证据可运行；受控命令/Receipt 要求精确来源和租户。BIND-1 31：CapabilityBinding create 必须引用 exact published CapabilityRevision/hash，当前 active readiness/六绑定另门。
- 原权威库只读：Installation 1条 rev1 draft→rev2 submitted→rev3 approved，`current_revision=3`,`active_revision=NULL`,`etag=3`；唯一 approved 决策绑定原 lock，runtime Binding 0。Growth bundle root 仅1.11.0；Capability Catalog 10条 published 也指1.11.0。`current_installation_release_evidence.py` 只读 view 可接受 approved 但显式标 `EVIDENCE_ONLY_NO_START`；`read_current_runtime_image_evidence` 要求 state active 且 active_revision=current_revision。故 b31 不通过改 Receipt 解除安装禁入。
- 原 `AipCapabilityBindingService.create` 已检查 Catalog exact id/revision/hash/published，并用同一事务结果版本写 Receipt；共享 `_insert_receipt` 创建 `resource_ref=Capability(asset_id,revision=None)`，`result_ref=CapabilityBinding(binding_id,revision=version)`。Catalog `(capability_id,revision)` 不可变，可把源 revision 写入已有 `ResourceRef.revision`，无需迁移；其他共享 operation 默认保持 None。

## 文件级步骤

1. 在 `services/aos-api/tests/aip/test_e17_s3ol_capability_issuer_pg.py` 现有真实独立非 owner issuer create 用例先 RED：`receipt.resource_ref` 必为 `Capability`、精确请求 asset_id 和 `str(revision)`；原 None 应失败。再复核持久回读、幂等重放相同 Receipt、dev-org隔离。
2. 最小改 `services/aos-api/aos_api/aip_agent_registry_store.py` 的 `_insert_receipt` 增可选 `source_revision`（默认None），`services/aos-api/aos_api/aip_capability_binding_service.py` 仅 create 传原 request 的 Capability revision。保持 result revision、普通 Agent/Skill/Run/Handoff 和 update/evaluate 原语义；不新增字段/DDL，不将 signed bundle版本混成 CapabilityCatalog revision。
3. 专项与相邻回归、`py_compile`/diff check、方案/代码复审、verification、m1 精确提交、01/06/D-waves/Prime更新。此波不写当前库；当前 approved3 无 active、正式 OIDC/issuer私有凭据/八配置/六Binding/Owner/Host 仍禁入。次波单独核 Receipt exact hash/当前安装 generation 证明与正式 role/operation scoped guard，不能拿此可选 revision 冒充首链。

硬边界：org-org/dev-project唯一正向、dev-org零副作用；不读商城源、不重放旧12 Run、不手工run_definition、不碰230 L0；当前库只读、Host/worker/Provider关、不push。
