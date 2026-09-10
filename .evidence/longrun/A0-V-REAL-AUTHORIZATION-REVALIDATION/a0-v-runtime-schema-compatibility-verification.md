# A0-V 电商 Runtime 结构兼容资格验证

## 1. 结果

`A0V_RUNTIME_SCHEMA_COMPATIBILITY_QUALIFICATION_GREEN`。

三个 runtime Candidate 均已携带签名内的结构兼容声明与唯一精确 requirement；v4 在当前 ReleasePolicy、schema requirement admission、OCI runtime admission 和 Composition resolver 下通过。该标记允许进入受控 canonical 首装，但不表示已经发布、安装、启用或获得业务执行权限。

## 2. 实现与边界

- `4943a36a`：为 core 1.1.0、niushop 1.1.0、growth 1.4.0 增加 `schema-compatibility.json` 与 `schema-requirements.json`，固定 Alembic `a0v_001` 和 13 个 `public` relation。
- `4f9eee9f`：构建 preflight 检查结构契约漂移；资格模式调用正式 `admit_schema_requirements`，并增加 compatibility/requirements 签名后篡改拒绝。
- `noPackageOwnedMigration=true`；本阶段没有连接数据库执行 DDL，也没有登记 schema receipt。
- Prime/OAuth 不参与制品、签名、准入或运行时逻辑。

改动路径：

- `bundles/candidates/ecommerce/domain.ecommerce.core/1.1.0/artifacts`
- `bundles/candidates/ecommerce/platform.ecommerce.niushop/1.1.0/artifacts`
- `bundles/candidates/ecommerce/solution.ecommerce.growth/1.4.0/artifacts`
- `scripts/build_ecommerce_runtime_candidates.py`
- `services/aos-api/tests/extension_runtime/test_runnable_ecommerce_candidates.py`
- `services/aos-api/tests/extension_runtime/test_ecommerce_runtime_candidate_builder.py`

## 3. v4 确定性构建

| 项目 | 值 |
|---|---|
| 源提交 | `4f9eee9f4480a2b589409116eda221fe618bbbe9` |
| build receipt SHA-256 | `b473385f353d28dfe5cd6a04cf4c8610c7b77496c7558e4f429271fa8a510638` |
| qualification receipt SHA-256 | `e8574f6b3bf2d7eb4d22bf811dc06174ffce18fe8f7f091a0bbebfd93f592da0` |
| repeat build receipt SHA-256 | `1e575223b443856afe83af8304c59ed19a17ca3cb0d3b137d8a6ad8caa6c2369` |
| staging tree | `sha256:26a5942e8087252df8f72e5430e4c4c6e42c906a8f814fe2df428d33c1293950` |
| SDK tree | `sha256:3f3639b97991ccf571d6f062e6345525c307e4c30f45e62335bb6d73620cd63b` |
| dependency lock | `sha256:7082d71d73dfa0ef7a607045bfa22242621728e3346d99542087d6c629fbcacb` |

两次独立构建使用端口 18442/18443；staging tree、四包 content hash、SDK tree、dependency lock、三个 image manifest digest 和 config digest 全部一致。回执中的 loopback `localRef` 端口按运行实例不同，不属于不可变 identity。

| Bundle | content hash | schema compatibility hash |
|---|---|---|
| `domain.ecommerce.core@1.1.0` | `sha256:cff310a440dcd75cd70cf8b31a56a237fccb39fabcdecda2b4ae3a1f77f4e4e1` | `sha256:d0c32b11ad733dd89e1f439a2d519a8716afe9d4bbfe8ce7ce8b01fa6cb933ee` |
| `platform.ecommerce.niushop@1.1.0` | `sha256:5a3e65d39ac276d2e9ab761835195fc3f5d9ace9d253b47368c5895c62402cd3` | `sha256:53bf3754b35dd941fe5410a5504035a73da716ef07c1d6c4d4184ea8a14389c2` |
| `solution.ecommerce.growth@1.4.0` | `sha256:23d432e1b01e5255d9c309a902dec30983366f8c2a6738854822fa5015790042` | `sha256:0ae03d2d1701ca1843565d41be75ffb181133ad208b7d2188e792ab53bb6dee4` |
| `solution.ecommerce.operations-base@1.2.0` | `sha256:eaf3a9ac9e0faca35246ed85d709ad97c8e1e8a4e5a7e315f1b4a0d6f896a298` | 不适用 |

## 4. 准入、自测与反证

- 四包解析为 core、niushop、growth、operations-base 精确版本，八个 Workshop module、三个 runtime member、12 条 registration operation。
- 三个 runtime 分别产生一个 `aos-platform-a0v-001` requirement，migration hash 与对应签名 compatibility artifact 字节摘要一致。
- 三个 OCI 均通过 signed image index、dependency lock、SBOM、manifest/config digest 与本地 immutable cache 校验。
- 七类签名后篡改全部被拒绝：image index bytes、image digest、dependency lock、SBOM、backend、schema compatibility、schema requirements。
- 相关专项测试 `89 passed`。另有七条既有 Pydantic/Starlette warning；进程退出时 JDBC 空缓存日志写入已关闭 stream 的告警为既有测试环境现象。
- 两份 build receipt 的四类效果计数均为 0：Registry publish、Installation mutation、Provider invocation、external publication。

## 5. 风险与下一步

结构 artifact 声明的是对宿主现有共享 schema 的精确依赖，不授予包执行迁移的权力。下一步 canonical 首装必须先在隔离恢复库验证数据库名、Alembic revision 和 13 个 relation，再以 maintenance-only 的只读 callback 登记三个 exact schema receipt；任一漂移都必须失败关闭。
