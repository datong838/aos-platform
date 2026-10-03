# W5CB4 E17-s3o-m｜Capability readiness 默认 owner 读取 RED

日期 2026-10-03。隔离 PG135，当前真实库只读；依据同名 plan、231-4/231-9、584/D-waves。

| 事实 | 可复核证据 |
|---|---|
| 原代码路径 | `AipCapabilityBindingService.__init__` 只把 `connect_factory` 给 Store，默认构造 `AipBindingReadinessService()`；后者默认 `PostgresBindingDependencyAuthority()` 与 `AipModelRuntimeStore()` 分别自取 `db_connect`。`evaluate` 先调用真实 readiness，`capability(ref)` 无 TenantScope 调用默认连接读取 CapabilityRevision；当前预览 DSN 为 owner `aos_app`。 |
| RED | 新测试用原 s3ol 自动销毁 PG 的真实连接包裹只读身份探针，真实 SQL `SELECT session_user,current_user` 回读 `[('aos_app','aos_app')]`；`pytest -q tests/aip/test_e17_s3om_capability_reader_pg.py --tb=short` → exit1，断言期望受限 `aos_aip_capability_issuer` 失败。评测未生成 Receipt，Binding version仍1。探针没有伪造 readiness 或 SQL 结果。 |
| 保留负例 | 该例设 strict xfail；与 s3ol/s3oj/s3oi 发行相邻运行 `.venv/bin/pytest -q tests/aip/test_e17_s3om_capability_reader_pg.py tests/aip/test_e17_s3ol_capability_issuer_pg.py tests/aip/test_e17_s3oj_skill_issuer_pg.py tests/aip/test_e17_s3oi_registry_issuer_pg.py --tb=short` → exit0，14 passed/1 xfailed。新测试 `py_compile`、`git diff --check` → exit0。当前服务未改，因此不为此测试重载 API。 |

结论：s3ol 的独立 writer 只证 create；原 evaluate 的 readiness reader 仍经预览 owner 兜底。不能把 CapabilityBinding evaluate/update 或正式 active 算通过；不能启 Host。此前签名预检与权威卷/全备未改变，当前 API PID45566 的健康/就绪/OpenAPI/Web200 是存活证据，不是本 RED 修复。

下波 E17-s3o-n 文件级修复入口：先定义全局 CapabilityRevision 的 scope-less 受限只读身份与租户依赖的 scoped 受限只读身份，拆清 `PostgresBindingDependencyAuthority`、`AipModelRuntimeStore`/Resolver 各自读取的表和 RLS；Service 显式注入，不得默认 owner。然后再扩 Capability issuer UPDATE，做原 evaluate blocked 持久化、CAS/幂等/撤销与失效负例。该波需要独立新计划和隔离 ACL，正式当前库迁移仍另波。
