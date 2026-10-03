# E17-s3o-w-ao-b30｜Capability CREATE 精确发布目录来源文件级方案

## 上位方案与当前实例只读事实

- 231-4：单一 PostgreSQL 权威、受控命令/精确列、非 owner、FORCE RLS 和全局串行迁移。BIND-1 §5/§6.1：CapabilityBinding create 必须引用 exact published CapabilityRevision/hash，随后才可做八维 readiness；catalog published 不授予运行权限。
- 2026-10-04 当前只读 SQL：`aos_current_preview_20260927@a0v_135` 有 10 条 `aip_capability_revision`，全为 published，`source_ref=SolutionPack/solution.ecommerce.growth/asset-registry/1.11.0`；Binding0、RegistryReceipt6，普通 runtime 对共享 Receipt INSERT=true。`.env` 指向的当前 bundle root 存在，Growth 子目录仅 `1.11.0`；当前 `bundle_installation` 1条，current_revision3、active_revision NULL。因此 published catalog 是可选定义，不是当前 active 安装/签名 Growth1.13 或首链授权。
- b22-b29 的 disposable PG 守卫已有独立 issuer/普通 runtime、初态/版本/一一回执/列形状负例，但 test helper 的 `capability_ref={}` 为刻意最小探针，不能作为真实 published 来源。原 `AipCapabilityBindingService.create` 在写前会核 catalog 精确 id/revision/hash 与 lifecycle=published；DB 直写当前缺此门。

## 文件级步骤

1. 只在 `services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py` 的 disposable full-schema DB 用原 catalog 列构造两条 test-only CapabilityRevision：一条 published、一条 evaluated；issuer仅授 catalog SELECT，无 catalog写/触发器禁用权限。测试 helper 改为 canonical `VersionedAssetRef` JSON keys，合法 create 指向 published 精确 id/revision/hash。
2. 先 RED：独立 issuer 以空 ref、未发布 ref、错 hash/版本/ID、假 resource type 直写 Binding 并配 create Receipt，应拒绝；当前守卫预计放行。最小修复仅 test-only BEFORE INSERT 查询精确 published Catalog 并要求 canonical字段，不改正式 Store/API/当前库。旧合法 create/update/evaluate、普通 Agent/Skill/Run/Handoff Receipt、既有负例须保持。
3. 复核 issuer 只能 SELECT catalog 且不能 DISABLE TRIGGER/修改 catalog，GRANT/POLICY 收尾清理；专项/相邻测试、静态检查、方案/代码复审、verification、m1精确提交、01/06/D-waves/Prime 同步。此波 catalog fixture不是当前签名来源；正式迁移仍需当前一致备份/ACL全恢复/历史行兼容/回滚/零执行窗口，Growth1.13、OIDC、Owner、八配置和六Binding分别补权。

边界：当前真实库只读；Host/worker/Provider关；org-org/dev-project唯一正向，dev-org零副作用；不读商城源、不重放旧12 Run、不手工run_definition、不碰230 L0、不push。
