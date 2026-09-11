# Runtime release artifact reader 方案

日期：2026-09-12

## 目标

提供正式 PreparationWorker 可复用的当前发布 release/制品读取器。record 必须来自持久 Registry 的 exact
published coordinate/content hash；artifact bytes 必须从同一批持久 `artifact_ref` 推导出的唯一
allowlisted `bundle://` source 读取，并匹配持久 digest。

## 军规

1. reader 在构造时固定 TenantScope、runtime connector 和 exact `ManifestLoader`。
2. 每次数据库读取使用独立 tenant transaction 与 `aos_runtime` 角色；不缓存 record、source 或 bytes。
3. `load_record(selected)` 只接受 exact `ResolvedBundle`，要求唯一 published row、identity/content hash 完全
   相等，复用 canonical `_record_from_row`。
4. `read_artifact(selected,path,limit)` 限制 path/limit，读取该 version 的全部持久 artifact metadata，要求
   每个 artifactRef 都严格以 `/relativePath` 结尾且前缀唯一；目标 path 必须唯一且 digest/size 合法。
5. 文件读取只调用 `ManifestLoader.read_verified_artifact(source_ref,path,expected_digest,limit)`；loader 的
   allowlist、路径和文件系统 identity 校验继续生效。读回 bytes 还要与持久 size/digest 再比较。
6. 不以作者树存在、active Installation、outbox 或测试 fixture 代替 published Registry 真值。

## 修改目录

- `services/aos-api/aos_api/extension_runtime/runtime_release_artifacts.py`
- `services/aos-api/tests/extension_runtime/test_runtime_release_artifacts.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md`

## 退出条件与下一波

exact record、source 一致性、digest/size/path/limit、租户/角色和零缓存反证通过，邻接 Registry/runtime
回归、hash、closure、提交完成。下一波用该 reader 组合 ProductionPreparationDependencies 与正式
PreparationWorker factory。
