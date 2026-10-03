# E17-s3o-w-am｜独立非 owner reader 撤销链验证

复习 231-9、AIP-7 22、BIND-1 31、s3o-w-al；先写文件级 plan，再在标准可销毁 `aos_test_*_ti4_test` 原表/原 RLS 上新增一条原受限 reader 实测。当前正式库只读，未建 role、未授 ACL、未写业务数据。

- 在隔离库创建 test-only frozen EvidenceBundle；`PostgresBindingDependencyAuthority(readiness_reader)` 的 session_user/current_user 均为独立 `aos_aip_binding_readiness_reader`、transaction_read_only=on，原 exact ref 正向可用；`org-org/other-project` 错租户不可见。
- 同一 exact `(org,project,bundle,revision,hash)` 写入原 append-only revoke event 后新只读事务拒绝。撤 `aip_evidence_bundle_revoke_event` 的 SELECT 后 `_require_identity` 抛 `READINESS_READER_DATABASE_IDENTITY_REQUIRED`，不回退到 owner 或普通 runtime。
- 目标 1 passed；相邻 `s3oo`/s3owal/Binding/Skill 四文件 30 passed、7 既有 warning，退出0；`py_compile`、`git diff --check` 退出0；测试结束后 `pg_database` 可销毁库残留0。

本波只增加隔离回归证据，无生产代码变更，服务已运行上一波 `m1@825066cf`，无需以本测试改动重启。正式当前库 `aos_aip_binding_readiness_reader` role 仍为0；正式 role/ACL、Provider OIDC/secret/健康容量、ToolBinding issuer/Receipt、六绑定/八配置与自然首链仍分别 pending。Host/worker/Provider保持关闭，不 push。
