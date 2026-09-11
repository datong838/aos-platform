# Runtime release artifact reader 验证

日期：2026-09-12

## 结论

新增 `CurrentRuntimeReleaseArtifacts`。它在 fixed TenantScope 的 `aos_runtime` 独立事务中读取 exact
published Registry coordinate/content hash，并复用 canonical record converter；转换后再次比较
publisher/id/version/contentHash。artifact reader 读取该 version 全部持久 metadata，要求 relativePath 唯一、
全部 artifactRef 同一 source，再调用 exact `ManifestLoader.read_verified_artifact`，最后二次比较 size/digest。

reader 零缓存；每次 record/artifact 调用重新读取持久真值。非法路径和 limit 在数据库访问前拒绝。

## 实测

- reader、ManifestLoader、Registry snapshot/revalidation、runtime admission/preparation/schema：94 passed。
- `py_compile`、`git diff --check` 通过。
- 覆盖 mixed source、错误 artifactRef、重复 path、缺失 path、size/digest 漂移、路径穿越、非 exact
  ResolvedBundle、零/多 published row 与转换后 identity 漂移。

7 条既有框架 warning 不改变 exit code 0。

## 一致性与剩余风险

- 实现满足 exact Registry 真值、唯一 source、allowlist 和零缓存方案。
- 本波没有单独新增完整 PG published fixture；数据库事务/角色边界复用已经真实 PG 覆盖的
  `consumer_connection`，SQL 与完整 signed lifecycle 的联合验证留给正式 worker composition 波次。
- production selector 尚未注入该 reader，未启动 OCI、未改 1.4.0、真实租户或业务数据。

## 下一波

新增 exact `ProductionPreparationDependencies` 与 per-tenant builder，组合 CurrentRuntimeReleaseArtifacts、
CurrentSchemaConditions、APPLY/VERIFY/ENABLE CurrentControlPermission、ReleasePolicy、OciDriver、platform 和
control-plane live directory；构造期保持零数据库/文件/OCI 访问。
