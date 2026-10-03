# W5CB4 E17-s3o-n｜自定义 Capability 发行连接 readiness 失败封闭

日期 2026-10-03。按同名文件级计划与 231/584/585，自动销毁隔离 PG135；当前权威数据库只读。

| 门 | 证据 |
|---|---|
| RED | 新测试 `test_custom_issuer_requires_explicit_readiness_before_owner_read` 在原服务 `preview` 未抛显式读者错误，pytest exit1；先前 s3o-m 原 evaluate 实测 `aos_app/aos_app` owner。 |
| 最小改动 | `AipCapabilityBindingService` 只在自定义 `connect_factory` 且未提供 `readiness_service` 时留空 reader；preview/evaluate/active 复核在 owner 默认读前抛 `AipAgentRegistryTransitionBlocked`。默认 preview 构造及 create/replay 不变，未把 writer 充当 reader。 |
| 正反回归 | `.venv/bin/pytest -q tests/aip/test_e17_s3om_capability_reader_pg.py tests/aip/test_e17_s3ol_capability_issuer_pg.py tests/aip/test_e17_s3oj_skill_issuer_pg.py tests/aip/test_e17_s3oi_registry_issuer_pg.py tests/aip/test_aip6_capability_run_handoff.py --tb=short -o log_cli=false` → exit0，21 passed/1 xfailed。新正例在 create 后对 preview/evaluate/active 拒绝，默认 reader 探针零次，Binding version1，无 evaluate/update Receipt；原独立 issuer create/replay 和相邻测试正常。原评测严格 xfail 继续保留待正式 reader。`py_compile`、`git diff --check` exit0。 |

复审：代码和方案一致，只阻断自定义 issuer 的隐式 owner readiness。当前默认预览构造仍有既有 `aos_app` 路径，不可据此申报正式受限发行；受限只读登录/精确 ACL、issuer UPDATE、原 evaluate 正向、当前库切换、八类配置和自然首链都未完成。此波不改真库、Host/worker/Provider，也不称 GREEN 为首链通过。下一波 E17-s3o-o 建立精确受限只读 reader 并显式注入；先只读表权/租户依赖盘点，再隔离原 blocked evaluate/CAS。
