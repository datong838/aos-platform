# E17 s3o-w-ao-b47：签名来源锁与受限命令组合计划

## 复习与选择

231-3/BIND-1 要求当前 active 安装和当期依赖在最终事务成立。b37 的 `_read_unique_active_in_transaction` 只给调用方当前签名证据；b41 test-only 受限函数能锁 exact active/current Installation 并与 Registry advisory `(228,1)` 协同；b46 test-only 受限命令能让调用者无 Binding/Receipt 表直写且失败时原子回滚，但固定 `blocked/TRUSTED_EVALUATOR_PENDING`，尚不核签名来源。当前正式凭据与 active Growth1.13 缺，真实库135只读。

## 文件级施工

1. 在 `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` 既有 Growth1.13 disposable signed/OCI 分支内复用签名 fixture 和随机低权角色；只新增有限的 Binding/Receipt 组合测试段，不改 1.11 路径、不重造签名 bundle。受限命令必须自己锁 exact org/project/installation/ETag 与 active=current，并与 b41 的 Registry 撤销锁顺序一致；调用方单独 Reader 证据不能作授权。若原测试过大，提取独立 test-only helper，但不重写安装基线。
2. 先 RED：受限命令不持安装行锁时，另连接可以在命令提交前完成 revoke/replace；随后在克隆补最低限度同事务锁并重验。两连接同时对 `bundle_installation FOR UPDATE` 和 Registry `(228,1)` 竞争，事务释放后允许继续；错 bundle hash、错安装/ETag、错租户、active/current 漂移均失败，Binding/Receipt 无半提交。
3. 本波只允许 b46 的 blocked/PENDING 输出，不接受任意 available/hash；b45 当期完整依赖计算、可信 evaluate 来源证明、正式 ACL/唯一136 仍后续独立门。若无法在函数里同时核 Registry 当前签名与 Catalog `source_ref`，如实留 RED，不用调用前独立 Python 检查替代。

## 验收

目标测试必须在完整 disposable PG/OCI、test-only 签名 Growth1.13 上跑专项和相邻回归；保留 b34/b37/b44 xfail，不启 Host/worker/Provider、不写当前库、不读商城源/旧12Run、不手工 Run、不碰230 L0、不 push。当前实例的身份与配置缺口只阻当前实例，独立产品配置研发继续。
