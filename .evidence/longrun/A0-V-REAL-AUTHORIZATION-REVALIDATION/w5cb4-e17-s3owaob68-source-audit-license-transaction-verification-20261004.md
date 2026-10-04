# b68 verification｜八类来源审计与 License 同事务首项证明

- Task `A0V-W5CB4-E17-S3OWAOB68-20261004`；先复习 231-3/BIND-1、b67 signed 联合测试与 `AipBindingReadinessService`、`AipModelRuntimeResolver`、预算/证据权威。八类代码来源/缺口矩阵见同目录 b68 plan。
- 已确认缺口：`PostgresBindingDependencyAuthority.exact_assets_available()` 对 Data/Tool 共用白名单，只有 `EvalDatasetRevision`、`EvidenceBundleRevision`；`aip_tool_binding` 记录 tool_id/version/status，无可与 `VersionedAssetRef.content_hash` 比对的 ToolRevision 真源。因此带 Tool exact ref 的 available 正向尚无合法依据；继续 blocked，不接受客户端 GUC/hash/伪 fixture。此为源码/DDL 审计结论，未声称所有八类当前实例均已配置。
- 隔离 PG 在 `test_e17_s3owaob45_transaction_readiness_pg.py` 新增 License Evidence 事务证明：未提交 frozen EvidenceBundle 且非空 license_summary，独立 Reader 仍报告 `LICENSE_EVIDENCE_MISSING`；`for_transaction(conn)` 可见并移除该项 blocker，整体仍 blocked；同事务插入精确 revoke event 后该 blocker 恢复，最后 rollback。测试只写 `aos_test_*_ti4_test`。
- `AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings --show-capture=no tests/aip/test_e17_s3owaob45_transaction_readiness_pg.py`：exit0，`2 passed/7 warnings`。`py_compile` 与 `git diff --check` exit0。
- 限制：该测试使用隔离库 owner 连接，仅证明已有 License Reader 的事务可见性与撤销判据，不证明正式 evaluator 低权角色具读权限、当前签名 License、八类 available、唯一136或当前库切换。b67 signed blocked 链和 Host 禁入保持。
