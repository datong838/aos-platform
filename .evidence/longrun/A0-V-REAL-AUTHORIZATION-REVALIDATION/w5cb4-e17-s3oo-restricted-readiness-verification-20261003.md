# W5CB4 E17-s3o-o｜Capability 原评测受限读取身份验证

日期 2026-10-03。依据同名计划、231/584～587。仅自动销毁 PG135；当前权威卷只读、Host/worker/Provider关闭。

| 门 | 可复核证据 |
|---|---|
| RED | 新 `test_e17_s3oo_capability_reader_pg.py` 初次 collection 因受限 reader 模块不存在 exit2；引入 reader 后原 evaluate 在授予 UPDATE 时被旧 create-only issuer ACL 拒绝，`REGISTRY_ISSUER_DATABASE_IDENTITY_REQUIRED` exit1；显式 lifecycle 命令族加入前仍 `REGISTRY_ISSUER_EXACT_CONNECTION_REQUIRED` exit1。没有使用 owner 作为成功替代。 |
| 受限 reader | 新 `aos_aip_binding_readiness_reader` 测试登录非 owner/非 runtime、无 BYPASSRLS、固定本机/库/私有 passfile，read-only REPEATABLE READ、精确超时/search_path；仅全局 CapabilityRevision 与实际 readiness 所需 16 个 tenant FORCE RLS 表 SELECT。无 scope 可读 catalog 但 tenant Dataset 0，org-org/dev-project 读自己1，other-project读0；所有 public 表无 DML/列表外 SELECT、无 schema/database CREATE。缺 catalog SELECT、跨域额外 SELECT、0644 passfile、PGPASSWORD 均拒绝。 |
| 原事务与相邻 | `AipCapabilityBindingService` 显式注入 Authority/ModelStore 同一 reader；原 create-only issuer 创建后，用同一独立登录的显式 `capability_lifecycle` ACL 门做原 evaluate。lifecycle 缺 UPDATE 或额外获得 DELETE 均被 ACL 拒绝。真实只读连接身份探针有 scope-less 和 scoped 两类，均 reader/read-only；缺正式依赖落 blocked、Binding version2/一份 evaluate Receipt；同键重放同 Receipt，旧 version CAS 冲突，active 被拒。旧 s3o-m owner RED 的 strict xfail 由上述正向覆盖并移除；未造 available/active。`.venv/bin/pytest -q` 对 s3oo/s3om/s3ol/s3oj/s3oi/BindingReadiness/AIP6 七组 → exit0，32 passed/7 existing warnings；`py_compile` 与 `git diff --check` exit0。 |

复审：读者无当前库凭据/角色，正式 API 路由仍是本机预览默认构造，未将新 reader 暗接旧 owner 路径；Capability create-only 发行门不接受 UPDATE，lifecycle 门必须显式选择且要求最小 UPDATE/no DELETE/no Receipt UPDATE。原租户/Receipt/CAS 正反逻辑未改。已知限制：本波只验证无 Route 的 blocked 评测，已填齐正式 Route/Policy/Provider/Gate 时的所有分支仍待独立构造与验证；多连接读取不是一个全局快照，激活复核/正式迁移需另门。不能将 test-only Capability、secretRef、数据集记作正式来源，也不能启 Host/自然首链。下一波继续当前正式 ACL/OIDC 凭证与入口/八配置的合法来源核验。
