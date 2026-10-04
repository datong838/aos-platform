# E17-s3o-w-ao-b32｜Capability create Receipt 来源配对隔离门

## 上位方案与当前事实

- 231-2/231-3/231-4 与 BIND-1：Catalog published、签名 Release、Installation active、Host Owner 是不同权威。Receipt 必须保留同租户、同事务、精确对象与版本；普通 Agent/Skill/Run/Handoff 的共享 Receipt 不得因 Capability 门失效。
- 当前配置 `AOS_BUNDLE_ROOT` 的 `solution.ecommerce.growth` 只有 `1.11.0`。原库只读显示 Capability Catalog 10 条 published 指向该版本；Installation rev3 approved、active_revision NULL，runtime Binding 0。无当前 Growth1.13 active/Owner 证明。b31 生产 create Receipt 已写 Catalog source revision，但 API 尚待最新栈重启加载。
- b30 的 disposable PG 已锁定 Binding capability_ref 必须精确命中 published Catalog；但隔离 Receipt guard 只检查 resourceType，create Receipt 可以把另一 source_id/revision 写成自己的来源。现有测试 helper 仍把 Binding id 写作 Capability 来源，需先以原 Service 的新形状建立正向基线。

## 文件级步骤

1. 仅修改 `services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py`：test-only helper 的 create 来源采用 published Catalog id/revision，普通共享 Receipt 与 update/evaluate 形状保持；增加独立 issuer 同事务 Binding+Receipt 的错来源 id、错来源 revision、缺来源 revision 负例。先 RED，证明原 guard 接受错来源。
2. 仅在同文件的 disposable PG deferred receipt guard 中把 create `resourceRef.resourceId/revision` 与 Binding `capability_ref.assetId/revision` 配对；沿用 b30 的 exact published/hash 检查。不得将 Catalog revision 当 bundle version，也不得用 test-only source 推导正式 Installation generation。
3. 专项/相邻回归、静态和方案一致性复审、verification、m1 精确提交，并更新 01/06、D-waves、续接和 Prime。当前原库只读，无正式迁移/API门变化；Growth1.13 signed release/OCI/trust/Owner 缺口登记为下一独立来源波。

硬边界：`org-org/dev-project` 唯一正向，`dev-org` 零副作用；Host/worker/Provider 关，不读商城源、不回放旧 12 Run、不手工 run_definition、不碰 230 L0、不 push。
