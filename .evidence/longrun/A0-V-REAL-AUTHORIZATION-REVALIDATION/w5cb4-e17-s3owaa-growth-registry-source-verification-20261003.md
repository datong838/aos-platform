# s3o-w-aa｜受限 BI 的 Growth 签名候选读取验证

## 范围与 RED

- 按同目录 `w5cb4-e17-s3owaa-growth-registry-source-plan-20261003.md`，只改 RegistrySnapshotReader、ApprovedBIPreparationResolver 的显式受限分支和隔离测试。原默认 SQL、ReleasePolicy、签名树校验不变。
- 第一轮 RED：受限 resolver 构造参数缺失，`TypeError`，退出 1；第二轮 RED：Python 分支接入后、受控函数创建前 resolver 仍为 `None`，断言失败，退出 1。未通过赋予 BI 四张 Registry 全局表 SELECT 来消除 RED。

## GREEN 与复审

- `cd services/aos-api && .venv/bin/python -m pytest -q tests/asset_registry/test_registry_snapshot.py tests/aip/test_aip_responsibility_template_authority.py`：47 passed，退出 0。
- 当前签名预检连接仅建立/销毁一次性 `aos_test_*_ti4_test` 库，显式设置 `AOS_EXTENSION_PG_TEST=1`、`AOS_EXTENSION_OCI_TEST=1` 及 Growth1.13 本地签名回执，再跑 `tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`：1 passed，退出 0，10.46s；先前加入 active 负例后一次同测 1 passed，退出 0，10.57s。
- `py_compile` 四个目标 Python 文件、`git diff --check` 均退出 0。
- 同一非 owner/NOINHERIT BI 登录由只读租户事务读取固定函数；函数在测试库为 `SECURITY DEFINER`、`STABLE`、`search_path=pg_catalog`，PUBLIC 无 EXECUTE，BI 角色独享 EXECUTE。四张全局 Registry 表 SELECT 仍全 false；只返签名 Growth1.13 当前锁内候选；未激活路径为空。错租户、NULL kind、伪造 hash、撤函数 EXECUTE 失败封闭；runtime 无 EXECUTE。原 ReleasePolicy 与本地 ManifestLoader 再核签名、digest、composition lock。

## 边界与下一门

- 函数 DDL 只在一次性库测试中创建并清理。当前权威库未迁移、未写入；正式角色到租户的持久映射、正式函数/ACL、独立凭据与 IdP、六 active Agent、原 Plan/Receipt 完整受限链均未证明。不能把 test-only 硬编码 org/project 的函数当正式 migration。
- 下一波 s3o-w-ab：把同一受限连接接入原 prepare/rebind 与 Receipt Reader，先隔离 RED，再核同键、并发、撤权、未知提交只读恢复。当前正式库变更须新一致备份、全链克隆和零执行窗口；Host/worker/Provider 保持关闭，首链 pending。
