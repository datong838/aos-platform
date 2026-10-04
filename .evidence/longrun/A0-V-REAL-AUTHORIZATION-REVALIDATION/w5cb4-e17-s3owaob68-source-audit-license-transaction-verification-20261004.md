# b68 verification｜八类来源审计与 License 同事务首项证明

- Task `A0V-W5CB4-E17-S3OWAOB68-20261004`；先复习 231-3/BIND-1、b67 signed 联合测试与 `AipBindingReadinessService`、`AipModelRuntimeResolver`、预算/证据权威。八类代码来源/缺口矩阵见同目录 b68 plan。
- **b69 纠错**：初版仅看 `aip_tool_binding` DDL，误称 Tool 无 exact 真源。W-D3 产品方案与 `aip_capability_tool_deps.py` 明确把十类 Capability 定义级 Tool ref 设为 frozen `EvidenceBundleRevision`，现有 `exact_assets_available()` 可按 revision/hash/frozen/revoke 校验。W-L20 `aip_tool_binding` 是实例执行分配，仍须另行核验；两层不得混同。本波 License 事务测试结果不受此纠错影响。
- 隔离 PG 在 `test_e17_s3owaob45_transaction_readiness_pg.py` 新增 License Evidence 事务证明：未提交 frozen EvidenceBundle 且非空 license_summary，独立 Reader 仍报告 `LICENSE_EVIDENCE_MISSING`；`for_transaction(conn)` 可见并移除该项 blocker，整体仍 blocked；同事务插入精确 revoke event 后该 blocker 恢复，最后 rollback。测试只写 `aos_test_*_ti4_test`。
- `AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings --show-capture=no tests/aip/test_e17_s3owaob45_transaction_readiness_pg.py`：exit0，`2 passed/7 warnings`。`py_compile` 与 `git diff --check` exit0。
- 限制：该测试使用隔离库 owner 连接，仅证明已有 License Reader 的事务可见性与撤销判据，不证明正式 evaluator 低权角色具读权限、当前签名 License、八类 available、唯一136或当前库切换。b67 signed blocked 链和 Host 禁入保持。
