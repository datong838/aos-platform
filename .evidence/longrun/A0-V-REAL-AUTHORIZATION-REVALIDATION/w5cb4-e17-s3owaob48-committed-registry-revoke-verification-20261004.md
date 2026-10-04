# b48｜已提交 Registry 撤销对受限 blocked 命令的负门

## 事实与复审

- 上位 231-3/BIND-1 要求当前安装/来源和 tenant Binding 当期依赖失败关闭，Receipt/CAS 同事务；b37 Python `ManifestLoader`/`ReleasePolicy` 真正验签，b45 同连接聚合，b47 只验证持久 composition 四键。先写 b48 文件级计划，再执行反例。
- 在完整 signed Growth1.13 disposable PG/OCI 克隆中，test-only 非 owner 命令原可在原 `RegistryService.revoke` **提交** Growth release 后仍根据持久 composition 写第二条 blocked Receipt，RED 为 `DID NOT RAISE InsufficientPrivilege`。这不会放开 available，但会把已撤销来源记入新的操作事实。直接改 status 的第一次 RED 被原 Registry 生命周期事件守卫 `CheckViolation` 拒绝；改用正式生产者完成反例。
- 最小修补只在 test-only SECURITY DEFINER 函数锁安装和 Registry advisory 后、Binding CAS 前，以 definer 最小 SELECT 核 `asset_bundle`/`asset_bundle_version` exact publisher/id/version/contentHash 且 `published` 恰一条；调用者无表写。正式撤销后调用 42501，Binding version 保持2、撤销键 Receipt0；调用者直接 UPDATE `available` 被拒。正常完整安装路径仍通过。此检查**仍不验**文件字节/信任根、evidence freshness、八类依赖，也未证明撤销与命令同时竞争的锁顺序；它只是已提交撤销的负门。
- 修改仅两个 test-only 文件，无生产服务/迁移/当前库写入。`AOS_B48_COMMITTED_REVOKE=1` 只控制隔离测试末尾的正式撤销；它不是验收 mock 或真实实例启动凭据。原完整测试默认路径维持。b34/b37/b44 strict xfail 未解除，available/Host 仍禁止。

## 可复核命令与退出码

| 命令 | 结果 |
| --- | --- |
| `AOS_DOTENV_DISABLED=1 AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_B48_COMMITTED_REVOKE=1 AOS_GROWTH113_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-growth-113-signing-receipt-20261002-r1.json PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --tb=short --disable-warnings --show-capture=no services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` | 最小修补前 RED exit1，`DID NOT RAISE`；修补后 exit0，1 passed/7 warnings（复跑追加直写 available 负例后亦 exit0）。 |
| 相同命令去掉 `AOS_B48_COMMITTED_REVOKE=1` | exit0，1 passed/7 warnings，原完整路径未回退。 |
| `AOS_E17_READONLY_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json services/aos-api/.venv/bin/python -m pytest -q --disable-warnings --tb=short services/aos-api/tests/extension_runtime/test_current_installation_release_evidence.py services/aos-api/tests/aip/test_aip_binding_readiness_service.py services/aos-api/tests/extension_runtime/test_release_revalidation.py` | exit0，32 passed/2 strict xfailed/7 warnings。 |
| `services/aos-api/.venv/bin/python -m compileall -q` 两测试文件；`git diff --check` | exit0。 |

## 未闭合与下一波

1. 本波是 `CHECKPOINT_GREEN_TEST_ONLY_COMMITTED_REVOKE_NEGATIVE_GATE_TRUSTED_READY_PENDING`，不是正式 trusted evaluate 或首链。需要可由 DB 验证、只对正式 evaluator 开放的同最终事务结果来源，且实际签名字节/信任根和八类依赖均来自该事务。不能把当前 test-only blocked 命令搬进唯一136冒充 available。
2. b49 应优先补**撤销/换代并发等待后重验**，核 Registry 生产者是否与受限命令使用共同锁；否则“已提交撤销”不足以覆盖同时竞争。再对仅持 EXECUTE 者试图绕过 Python Reader 写 available 做明确负门/可信协议。若正式正向需要136，先独立一致备份、全恢复克隆、零执行窗口；当前库135仍只读。
3. 正式 OIDC/Issuer/Reader/Owner、active Growth1.13、八配置/六 Binding 与自然首链仍缺；Host/worker/Provider关。每日提醒另做最新全栈重启，不因本波测试等同重启。
