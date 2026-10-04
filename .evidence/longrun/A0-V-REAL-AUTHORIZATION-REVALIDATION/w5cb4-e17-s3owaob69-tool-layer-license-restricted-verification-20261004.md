# b69 verification：签名隔离安装中的 License 受限读取

## 基线与变更

- 方案：同目录 `w5cb4-e17-s3owaob69-tool-layer-license-restricted-plan-20261004.md`。复核 W-D3（92）和 W-L20（128）：定义级 Tool 使用 frozen `EvidenceBundleRevision` exact ref；实例级 `aip_tool_binding` 是独立运行分配。b68 初版误判已在代码/上下文追溯纠正。
- 仅改两个测试文件：`services/aos-api/tests/extension_runtime/plan_restricted_evaluate_case.py` 与 `test_growth_signed_installation_full_schema_pg.py`。新增 opt-in `AOS_B69_LICENSE_AUTHORITY=1`；默认签名路径不改。隔离 `aos_test_*_ti4_test` 使用本地 test-only 签名 Growth 1.13、真实 schema 与 OCI。
- 受限命令在已锁当前 Installation/Registry 后，以固定 id/revision/content_hash 读取 frozen、非空 license_summary 的 EvidenceBundleRevision 和撤销事件。普通调用者不能传入 hash、状态或 GUC 作为授权事实。

## RED/GREEN 与新鲜验证

- RED：未授予 definer 两张 Evidence 表 SELECT 时命令报 `InsufficientPrivilege`；Binding 仍 version 1，所用幂等键 Receipt 0。
- GREEN：只授予 SELECT 和租户 RLS 后，原命令生成 **blocked** Binding version 2 和成对 Receipt。已提交 exact revoke 后新命令拒绝，Binding version 2、该键 Receipt 0。
- `AOS_B69_LICENSE_AUTHORITY=1 ... python -m pytest -q .../test_growth_signed_installation_full_schema_pg.py`：退出 0，`1 passed, 7 warnings`（本轮重跑）。省略 b69 开关的默认签名路径同命令：退出 0，`1 passed, 7 warnings`。
- `python3 -m py_compile` 两个文件及 `git diff --check`：退出 0。b67 paired Receipt 路径在本次代码后已单独通过（`1 passed, 7 warnings`，上一轮执行）。

## 方案/代码复审与剩余风险

- 测试只证明已提交撤销后的失败关闭与受限事务中 License 来源可见性；未证明并发撤销锁序、其他七类来源同最终事务、W-L20 实例 ToolBinding、当前正式三身份/Host Owner 或自然首链。
- 测试专用 SQL 和临时角色只存在可丢弃隔离库；当前真实库 a0v_135 只读，Host/worker/Provider 关闭。不把 test-only 证据当正式实例授权；不读商城源、不重放旧 Run、不手工 run_definition。
