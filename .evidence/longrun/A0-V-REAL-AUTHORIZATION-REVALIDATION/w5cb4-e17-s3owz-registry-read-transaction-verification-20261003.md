# s3o-w-z 第一切片 verification｜原签名 Registry 受限事务协议

- 基线 `m1@a543c837`、Authority `AOS-001240`。复习 231-3/231-9、原 `ApprovedBIPreparationResolver`、`RegistrySnapshotReader`、BI DB 身份门、签名 full-schema 克隆。先写方案；首次 RED 的 test fixture 误用了会预启动事务的 `aos_api.db.connect`，改为原生 psycopg 新连接后发现无条件 SET 对部分已有事务允许变更，不能把 PostgreSQL 是否报错当作准入门；明确修订方案为显式模式。最终 RED 为 `RegistrySnapshotReader.__init__` 不接受 `prepared_transaction=True`，exit1。
- 最小实现：`RegistrySnapshotReader` 新增显式布尔，默认 False 保持原 SET；True 只接受真实 psycopg 已启动的 REPEATABLE READ/READ ONLY 事务，否则拒绝。`ApprovedBIPreparationResolver` 只传递显式 `registry_prepared_transaction`，默认 False；不依据 GUC/env 自动放行，不 commit 破坏租户绑定。
- `tests/asset_registry/test_registry_snapshot.py tests/aip/test_aip_responsibility_template_authority.py`：46 passed，exit0；新 PG 正例和 READ COMMITTED/非只读负例，旧 Registry 测试全部通过。
- 原签名 Growth1.13 full-schema disposable DB 1 passed，exit0，当前库只供签名预检，未写。prepared read-only resolver 在隔离库中对原签名模板正向；但原 test-only BI 登录调用 resolver 仍返回 None，精确 `has_table_privilege` 表明其对 `asset_bundle`、`asset_bundle_version`、`asset_bundle_artifact`、`asset_bundle_evidence` 四表均无 SELECT。原 owner/runtime 读者正向不能冒充独立 BI 登录完整正向。当前真实库正式 BI 登录/四受控函数/active Agent 均0，HTTP503/Host关、首链 pending。
- 代码/方案复审：新增显式模式不改变默认生产 Registry 行为；不能为了过测直接给 BI 登录四张全局表宽 SELECT 或 owner/runtime 成员。下一切片要设计精确签名 Growth 候选的最小受控读取，与原 resolver/RegistrySnapshot 的同一受限身份组合，再考虑有限 accept/原 Receipt 对账。此波无 UI 改动，浏览器不适用。
