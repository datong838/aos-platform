# W5CB4 E17-s3o-m｜CapabilityBinding readiness 读取身份 RED 计划

日期 2026-10-03。依据 231-4 受限查询与租户权限、231-9 首链真实证据、584 和 D-waves s3ol。先只在自动销毁 PG135 精确验证原 `AipCapabilityBindingService.evaluate` 的实际 reader 身份；不碰当前库、Host/worker/Provider。此波若复现 owner 兜底，先保存 RED 与原服务必要依赖图，再另波最小接线，不能靠 mock readiness 或 test-only 数据申报完整评测。

原路径：Service 注入 `connect_factory=capability_issuer` 仅被继承的 Store 写事务使用；默认 `AipBindingReadinessService()` 又默认建立 `PostgresBindingDependencyAuthority()` 和 `AipModelRuntimeStore()`，两者各自取 `db_connect`。`evaluate` 在写前先 `get`，然后 `_authority.capability(ref)` 会通过无 scope 的默认连接读全局 CapabilityRevision。当前预览 DSN 是 owner `aos_app`，因此即使写者已独立，readiness 可由 owner 兜底。空依赖可避免 Provider 外部调用，却仍发生该读取。

文件级：新增 `tests/aip/test_e17_s3om_capability_reader_pg.py` 复用 s3ol 隔离夹具；使用包裹真实 `db_connect` 的只读探针记录 `session_user/current_user`，不替代 SQL 或返回假数据。原 create 后调用原 evaluate，预期读取身份应是受限 issuer；先运行测试 RED，回读真实身份、绑定/Receipt 状态。保持 strict xfail 记录缺口。不会把 `aos_app` 读取算受限业务验收。

后续最小修复候选需逐项核：全局 CapabilityRevision 的受限 scope-less SELECT 应使用明确平台只读身份；租户依赖 reader 使用精确 TenantScope、只读事务、FORCE RLS，ModelRoute/Policy/Provider、Eval Gate/Contract、Evidence/资产引用均列出表权；Service 需显式注入而非隐式 default。修复必须在新计划中确定读身份和文件范围，再做 RED→最小实现→专项/相邻回归。当前卷迁移仍按新全备、ACL-faithful 克隆、零执行窗口与正式凭证另波。
