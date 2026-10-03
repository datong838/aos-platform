# E17-s3o-w-ao-b29｜Capability CREATE 初态与来源文件级方案

## 上位方案与当前事实

- 231-4 的受控命令列/谓词、非 owner、FORCE RLS及串行迁移；BIND-1 31 的 tenant CAS/幂等 Receipt 与只绑定已发布 Capability。原 `AipCapabilityBindingService.create` 先查 `aip_capability_revision` 的精确 id/revision/hash 且 lifecycle=published，再以 status=provisioning、health=unknown、version=1 写 Binding 和同事务 Receipt。
- `aip6_001` Binding 仅限制 status/health 枚举、version>=1，并无默认初态/发行来源约束；b24-b28 的 test-only BEFORE marker 在 INSERT 直接归类 create。正式原库/代码头仍135、Binding0/Receipt6，当前写503且库只读。

## 文件级与判据

1. 先在 `services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py` 的 disposable full-schema PG 加 RED：独立 issuer 插入 status=active 或 version=2 的 Binding，并配同版本 create Receipt，必须拒绝。合法 provisioning/unknown/version1 的原正向及普通共享 Receipt保持。
2. 最小 test-only 修复 INSERT 标记：只接受初态 provisioning/unknown/version1，`observed_at`、`last_evaluated_at`、`dependency_snapshot_hash` 未预填；其余按 b28 UPDATE 精确列矩阵继续。不能把这个形状检查冒充签名来源：现有 test helper 的 `capability_ref='{}'` 只用于守卫探针，不代表真实已发布 Capability。
3. 隔离负例后单独审正式来源所需的精确 `(capability_id,revision,content_hash,lifecycle=published)` 权限与 FK/受控命令证据，再决定是否改 test helper 和迁移候选。专项/相邻回归、复审、verification、m1提交、01/06/D-waves/Prime更新；当前库不写、正式 API/Host不启。

边界：org-org/dev-project唯一正向，dev-org零副作用；不读商城源、不回放旧12 Run、不手工run_definition、不碰230 L0、不push。新 Alembic 头进m1前仍需独立新备份、全恢复、迁移/回滚及零执行窗口。
