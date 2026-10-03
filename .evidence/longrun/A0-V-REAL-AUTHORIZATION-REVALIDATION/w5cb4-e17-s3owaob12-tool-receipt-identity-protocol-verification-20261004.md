# E17-s3o-w-ao-b12｜Tool Receipt 双向事务身份隔离验证

## 方案复审与 RED

- 按 231/BIND-1 与 b6/b8 方案先读原 ToolBinding/RegistryReceipt 表和两条发行 strict xfail。回读 s3o-w-p 至 s3o-w-ad 证明 b12 原计划中的 BI 安装锁接线早已完成，已先修订计划，不重复该切片。
- 新增 `services/aos-api/tests/aip/test_e17_s3owaob12_tool_receipt_identity_pg.py`，由 pytest 标准 fixture 创建完整 `a0v_135` 一次性 `aos_test_*_ti4_test` 库；仅在此库创建随机 NOINHERIT 非 owner issuer/runtime 登录、精确 SELECT/INSERT 与租户 RLS。原共享 Receipt 在两种登录可 INSERT 时，尚无 Tool operation guard：runtime 插入 `tool_binding.upsert` 未被拒，目标首跑 `1 failed`/exit1（`DID NOT RAISE InsufficientPrivilege`）。这是 DB 协议缺口，不是当前正式 Tool 来源。

## 隔离协议与回归

- test-only Receipt `SECURITY INVOKER` trigger：只让真实 `session_user` 为 Tool issuer 的连接写 Tool operation；绑定行 type/id/revision/tenant 与当前事务行版本 `xmin` 精确配对，issuer 写其它 operation 拒绝，runtime 原普通 operation 保留。初版 `SECURITY DEFINER` 因 ToolBinding FORCE RLS 看不到已插入行，真实正向失败；改为 INVOKER 后原 issuer 的受限 SELECT/RLS 可见。未将这段 SQL 写成迁移或生产代码。
- test-only ToolBinding deferred constraint trigger 在提交时反查同事务发行 Receipt：无 Receipt 的绑定 INSERT 被回滚；配对 INSERT+Receipt 同事务通过。runtime Tool operation、`SET ROLE issuer`、issuer 无配对/错版本/错租户/旧行事后补 Receipt/重复写，以及一次性事务回滚均拒绝或不留配对。正向仅为 `disabled`、`test-only-tool` 隔离形状，不能证明正式 active ToolDefinition/Owner/安装 epoch。
- 目标 `1 passed`/exit0；相邻原 Tool 发行/Assignee 测试 `8 passed, 1 xfailed`/exit0（旧 xfail 仍是真缺口）。`py_compile`、`git diff --check` exit0。测试 finally 清理两个 trigger/function、policy/GRANT/随机 role；会话级一次性库由 pytest fixture 删除。无当前权威库、API/Web 或浏览器改动。

## 方案一致性与剩余风险

- 这只验证原表在一次性库中可用**双向** DB 约束维持 operation/session/同事务配对；`xmin` 属于隔离探针，尚未冻结为生产持久协议，须复审 xid wraparound、更新、历史行与并发。原 Store 仍使用普通连接且无同事务 RegistryReceipt；当前四 signed bundle 无 ToolDefinition，正式专用身份/凭据/Owner、共享 Receipt 对其它生产者的权限相容性及当前库迁移/切换均未完成。不得以本波测试宣称正式 Tool 发行、六 Binding 或自然首链通过。
- 下一波先定正式 signed ToolDefinition/发行/撤销来源合同与专用 issuer 对现有 operation 的兼容矩阵；若正式来源缺失，转已登记合法配置来源/当前实例身份链的安全项。当前真实库只读、Host/worker/Provider关，Goal active、不 push。
