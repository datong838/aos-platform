# E17-s3o-w-ao-b47｜隔离签名安装锁与失败关闭命令组合

## 复审结论

- 复习 231-3/BIND-1、b37 当前签名 Reader、b41 受限安装锁和 b46 原子失败关闭命令后，先写文件级方案，再在现有 disposable full-schema/OCI 的 test-only signed Growth1.13 安装测试里调用独立 test-only helper。原 1.11 路径、生产服务与迁移未改。
- b47 helper 的随机 NOLOGIN/NOBYPASSRLS definer 只获安装/组合三表 SELECT、Binding SELECT/UPDATE、Receipt SELECT/INSERT 和精确租户 RLS；随机非 owner 调用者对 Binding 无 UPDATE。`SECURITY DEFINER` 函数检查 session_user、租户 GUC、SERIALIZABLE、安装 id/ETag；调用 b41 受限行锁后持 Registry advisory `(228,1)`，再核当前 composition lock 的 Growth publisher/id/version/hash，仅可写 `blocked/TRUSTED_EVALUATOR_PENDING` 和空 snapshot/expiry，随后 Binding CAS/Receipt 同事务。
- 正向测试故意**不调用** Python 签名 Reader 即执行该函数：说明 SQL 组合锁虽能固定已持久的来源身份，却不能证明 `ManifestLoader` 文件字节和 `ReleasePolicy` 信任根实际被重验。由于结果永远 blocked，这个隔离原子性试验不构成可用性授权。要开放 available，仍需可信签名/依赖评估证明与最终事务不可伪造绑定；不能凭当前 SQL source count 替代。b34/b37/b44 xfail 保留。
- 同事务未提交时第二连接看不到 evaluate Receipt，安装行 `FOR UPDATE` 与 Registry advisory 均 250ms 超时；提交后 Binding version2、状态仍 provisioning、readiness blocked、snapshot NULL，Receipt恰一条；错误安装 id 拒绝且版本仍2。无 EXECUTE 拒绝，test-only 函数/策略/角色 finally 清理，真实库只读。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| 完整 signed Growth1.13 disposable PG/OCI 测试（见 b47 plan 所列完整环境变量与命令）修改前 | exit0，1 passed/7 warnings，15.18s。 |
| 加 helper import、尚无 helper 文件 | RED exit2，`ModuleNotFoundError: plan_restricted_evaluate_case`。 |
| 同完整命令实现后最终复跑 | exit0，1 passed/7 warnings，15.71s。 |
| `AOS_E17_READONLY_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json services/aos-api/.venv/bin/python -m pytest -q --disable-warnings --tb=short services/aos-api/tests/extension_runtime/test_current_installation_release_evidence.py services/aos-api/tests/aip/test_aip_binding_readiness_service.py services/aos-api/tests/extension_runtime/test_release_revalidation.py` | exit0，32 passed/2 strict xfailed/7 warnings。 |
| `python3 -m compileall -q` 两个修改的测试文件，`git diff --check` | 均 exit0。 |

## 下一门

1. 不能直接把 b47 test-only definer 放进唯一136；它未验签名字节/信任根，也没执行 b45 当期模型、评测、许可、数据、工具、预算全依赖。下一波须先做可验证的**受信评估来源协议**：当前签名 Reader/所有依赖在同一最终事务中完成、只有经过该路径的结果才能触发受限命令，独立账号/可写 GUC/纯行形状不能伪造。
2. 补两连接已提交 revoke/replace 的锁后重验、失败回滚和 available 正向；正式 role/OIDC/Owner、active Growth1.13、八配置/六 Binding 及首链仍无当前证据。当前权威卷135只读、Host/worker/Provider关，每次每日提醒另完整重启，Goal active、不 push。
