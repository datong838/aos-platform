# E17-s3o-w-ao-b35｜Capability 当前签名来源合同前置

## 当前事实与边界

- b34 把 Catalog 原 `source_ref` 带到 readiness Reader，未授权 active；严格 xfail 证明来源失效仍可被假定依赖齐备的就绪评估误判 AVAILABLE。当前真实库 Catalog10条 `SolutionPack/solution.ecommerce.growth/1.11.0/asset-registry`，来源 ref 不含签名包 content hash；原签名 Release 1.11.0/approved3/active NULL，Growth1.13 当前发布与 Owner 缺。
- BIND-1 create→provisioning 可用 published Catalog；activate 与 runtime start 需要签名/安装/撤销/依赖重验。231-2/3 要求最终同代事务检查，不以旧只读快照跨事务授运行权。

## 文件级施工选择

1. 先核原 Catalog 发布生产者是否保存精确 release content hash 或签名 publication Receipt；只读查 schema、原发布代码与当前版本行，不读取商城源或密钥。若仅 source_ref 的 id/version 可由发行者自报，则不把它当签名字节证明。
2. 在 `services/aos-api/tests/aip/test_aip_binding_readiness_service.py` 和现有签名 full-schema 测试中冻结 source_ref 错版本/撤销/旧 installation generation 的 RED；不能用假 `capability_source_current=True` 宣称正向。若现有 schema 无法表达同源证明，先补文件级迁移和权限/回滚合同，再用 test-only 克隆证明，当前真库保持只读。
3. 生产候选在 `aip_binding_readiness_service.py` 与 `extension_runtime/current_installation_release_evidence.py` 之间复用现有只读 Reader，不新增第二真源；必须在激活/运行最终事务重验，普通 create 保持。正式来源缺时 current 实例继续禁入，转做独立 Receipt operation 施工。

收到每日提醒时立即做一次最新 m1/权威卷完整重启，先核备份/迁移/签名，Host/worker/Provider仅正式授权齐后启。`org-org/dev-project`唯一正向，`dev-org`零副作用，不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
