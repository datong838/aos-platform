# 栖月汇恢复 core 继任候选实施合同

依据当前恢复方案和 AOS-001838：历史已发布 core1.4.0 哈希与当前构建不同，禁止覆盖旧 coordinate。独立 unsigned core1.4.3 仅修改 manifest version；完整 backend、ontology、schemas、policies、schema requirements/compatibility 字节保持。基线 treeHash 9136eeb54182a941908da64f9a7f7cce7fd939ab911f603f49d6c08b66748115。基线无 bundle selfref。

新增 scripts/prepare_ecommerce_qyh_recovery_core_candidate.py，采用临时 staging、全量基线复查、拒绝已有目标；移除旧 eval/SBOM/signature/image/dependency 构建证明，写 UNBUILT_UNSIGNED provenance。不复制旧 passed 作为继任验收。

新增 scripts/build_ecommerce_qyh_recovery_candidates.py，复用原 Growth1.13 builder，仅替换 core tuple，保留 platform1.23.0/Growth1.13.0/operations1.2.0。加载时核验继任所有文件与固定基线差异集合、旧 profile inventory；原 preflight 验证15 operations/8 modules/8 routes。只在构建输出生成 core 源级 preflight eval 和空组件 SBOM，由原 augment 补 SDK/base；此 eval 明确非 runtime/business 验收。构建 profile 原 source 不写。

新增 services/aos-api/tests/extension_runtime/test_qyh_recovery_candidates.py：先 RED，覆盖目标不覆盖、基线/候选漂移拒绝、源码和 metadata 差异、构建 inventory、原 profile 保持、输出证据边界。相邻原 Growth1.12/1.13 测试；方案/代码复审和 precise Delivery。纯包准备不涉及 UI，浏览器验收不适用，不宣称页面恢复。

下一步是真实隔离构建/qualification/tamper，后续当前正式发布/配置/HTTP恢复和实际八工作台验收仍需独立门；本波不签名、不发布、不操作正式库、运行任务或商城数据。
