# E17-s3o-w-ao-b35｜Capability 当前签名来源合同前置

## 当前事实与边界

- b34 把 Catalog 原 `source_ref` 带到 readiness Reader，未授权 active；严格 xfail 证明来源失效仍可被假定依赖齐备的就绪评估误判 AVAILABLE。当前真实库 Catalog10条 `SolutionPack/solution.ecommerce.growth/1.11.0/asset-registry`，来源 ref 不含签名包 content hash；原签名 Release 1.11.0/approved3/active NULL，Growth1.13 当前发布与 Owner 缺。
- BIND-1 create→provisioning 可用 published Catalog；activate 与 runtime start 需要签名/安装/撤销/依赖重验。231-2/3 要求最终同代事务检查，不以旧只读快照跨事务授运行权。

## 文件级施工选择

1. 先核原 Catalog 发布生产者是否保存精确 release content hash 或签名 publication Receipt；只读查 schema、原发布代码与当前版本行，不读取商城源或密钥。若仅 source_ref 的 id/version 可由发行者自报，则不把它当签名字节证明。
2. 在 `services/aos-api/tests/aip/test_aip_binding_readiness_service.py` 和现有签名 full-schema 测试中冻结 source_ref 错版本/撤销/旧 installation generation 的 RED；不能用假 `capability_source_current=True` 宣称正向。若现有 schema 无法表达同源证明，先补文件级迁移和权限/回滚合同，再用 test-only 克隆证明，当前真库保持只读。
3. 生产候选在 `aip_binding_readiness_service.py` 与 `extension_runtime/current_installation_release_evidence.py` 之间复用现有只读 Reader，不新增第二真源；必须在激活/运行最终事务重验，普通 create 保持。正式来源缺时 current 实例继续禁入，转做独立 Receipt operation 施工。

收到每日提醒时立即做一次最新 m1/权威卷完整重启，先核备份/迁移/签名，Host/worker/Provider仅正式授权齐后启。`org-org/dev-project`唯一正向，`dev-org`零副作用，不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。

## 原代码与 schema 复核后的合同修订（先于编码）

- `aip_solution_pack_signed_preflight.CurrentDefinitionSourceProof` 在发布前有 content hash、签名指纹和 Registry 快照 hash；`AipSolutionPackPublisher.publish_current_verified` 只校验其对象形状后调用逐项 `_publish`，没有把 proof 与十个 Catalog 行放入同一不可变事务。`aip_capability_revision.source_ref` 只有 `SolutionPack/id/version/asset-registry`，表内 `content_hash` 是 Capability 定义 hash，不是 bundle hash。现状不能从发布行反推出哪一份签名字节，也不能把旧预检对象视为持续授权。
- 最小正确数据合同应是**不可变、精确到每一 Catalog revision 的来源 Receipt**：source publisher/id/version、bundle content hash、签名指纹、Registry release revision、Catalog id/revision/hash、发布 operation/idempotency、actor 与 DB 时刻，并与对应 Catalog 插入同事务固化。复用现有 Catalog 及 Registry/Installation 表，不修改旧 Capability hash、旧包 manifest 或普通 `create→provisioning` 语义。新增来源 Receipt 的普通 runtime 写权默认无，正式发行角色单独限权；历史行不推断回填，只有正式重验并受控补证后才可授权。具体迁移号、角色和回滚在下一安全波先用 test-only 克隆验证，当前真实库只读。
- 就绪 Reader 需从 Receipt 精确配对 Catalog 行，再用当前租户 Installation lock 选中同 publisher/id/version/hash/fingerprint，重验 Registry 发布/撤销/签名原字节；缺任一项、错 hash、旧 release、撤销、Installation 非当前代均给 `CAPABILITY_SIGNED_SOURCE_UNAVAILABLE`。`CurrentInstallationReleaseEvidence` 可复用签名和 lock 校验，但其返回值明示 `EVIDENCE_ONLY_NO_START`，不得当成 runtime 许可。
- 激活与每次 runtime invocation 的最后许可边界仍须**在同一数据库事务**持有精确 Installation/binding/fence/current permission 的读锁或等价 CAS，再重算来源与依赖；`AipCapabilityBindingService.update(active)` 目前调用跨连接的 readiness 服务，即使先加 Reader 也存在 TOCTOU，故不能提前消除 strict xfail。先做 Receipt 持久合同、低权负例，再接最终事务重验。当前实例原 Catalog 无该 Receipt，继续禁入。
