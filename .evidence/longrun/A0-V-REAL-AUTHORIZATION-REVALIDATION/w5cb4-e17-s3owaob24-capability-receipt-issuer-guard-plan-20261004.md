# E17-s3o-w-ao-b24｜共享 Receipt 精确发行守卫文件级方案

## 已读依据与现状

- 231-4 规定共享 PostgreSQL 表所有权、租户 RLS、审计身份与 runtime 身份分离；BIND-1 31 要求 CapabilityBinding expected-version CAS、幂等 Receipt。b22 `m1@ca7ec63a` 一次性 test DB 证明真实独立 issuer 与双向事务守卫的安全形状，但用的 `xmin` 只是隔离探针；b23 `m1@aae68ee2` 已让三类新 Receipt 的结果版本取真实落库 `RETURNING version`。
- 当前真库 `a0v_135`、正式 Reader/Capability issuer角色0；当前签名预览 Capability 写503，Receipt6/Binding0，Host/worker/Provider关。a0v_135 的 downgrade 明确失败关闭，不能为跑旧测试放宽 ACL。当前备份/完整恢复和最新栈证据见 b23 verification。
- 共享 `AipAgentRegistryStore._insert_receipt` 还由 AgentInstance、Skill、Run、Handoff、Execution 子类调用；其他服务也有自己的 Receipt 写入函数。不能仅按 Capability 三个 operation 撤全表 runtime INSERT 或套全表触发器。

## 只读 operation/身份矩阵（本波复核）

| 共享表写者 | 当前代码 operation | 本波边界 |
| --- | --- | --- |
| AgentInstance | `agent_instance.create/update` | 普通 runtime 兼容；当前真库六条均为 create |
| SkillBinding | `skill_binding.create/update/evaluate` | 普通合法操作不能被 Capability 守卫误挡 |
| AgentRun | `agent_run.create/cancel_queued` | 保留原 Receipt 写序与幂等重放 |
| ExecutionAttempt | `agent_run_execution_attempt.create` 及状态枚举衍生操作 | 枚举值需随完整回归验证，不硬编码为 Capability 白名单 |
| Handoff | `handoff.issue/decision` | 保留原权限与租户 RLS |
| CapabilityBinding | `capability_binding.create/update/evaluate` | 唯一拟限制为独立发行者与同事务 Binding 版本配对的前缀 |

`aip6_002` 共享表有 `(org_id,project_id,operation,idempotency_key)` 唯一约束、FORCE RLS/租户策略、append-only；`aos_runtime` 仍获 Receipt INSERT 与 CapabilityBinding INSERT/UPDATE。当前真库 `aos_runtime` 对库 CONNECT=false，正式 Capability issuer role=0；不能由表 ACL 推断当前直接可登录攻击，但 owner `SET ROLE` 的 b19 负证据仍成立。`a0v_135` 禁止降级针对 extension schema ACL，不应误写为已封 Capability Receipt。

b22 test-only Receipt 守卫在 `BEFORE INSERT` 检查同事务 Binding 的 `xmin`；若先更新 Binding 到新版本，再插入合法 update Receipt 和**额外伪 create Receipt**，当前守卫可能只因同事务版本相同而接纳额外 create。还要检查反序插入后更新；正式协议必须区分 INSERT/UPDATE 事件并在事务末验证最终版本，不能只凭结果 ID/版本与 `xmin`。

## 文件级次序

1. 只读形成 operation/写者/真实 DB LOGIN/tenant/结果引用/幂等重放矩阵：检查 `aip_agent_registry_store.py`、Capability/Skill/Run/Handoff/Execution 服务、Receipt 表迁移与历史只读回执。列出未覆盖 operation，不以少数例子推全表合法范围。
2. 在 `services/aos-api/tests/aip/` 一次性全迁移 test DB 写真实独立登录 RED：普通 runtime 写无配对 Capability Receipt、issuer写非 Capability 或错租户/错版本/旧事务、Binding 无 Receipt、撤销后的补写；普通 Agent/Skill/Run 现有 operation 正向必须保留，失败不能仅因测试夹具缺权限。
3. 比较持久配对选项。任何依赖可修改 session GUC、owner `SET ROLE`、仅在 commit 后对历史行补 Receipt、仅凭 `xmin` 的方案均不得直接部署。先冻结可靠同事务标记、精确 issuer 私有凭据、RLS/ACL/撤销与 rollback 合同；若需公共协议裁决，明确待决并继续八候选/六 Binding 独立代码项。
4. 仅合同充分时，先 test-only 守卫正反证明，再按最小生产迁移/服务接线、专项与相邻回归；当前卷迁移另需新一致全备、独立完整恢复、零执行窗口。若生产代码变化，严格 PG→API→Web 最新 m1 重启并浏览器复验。verification、精确提交、01/06/D-waves/Prime 收口，进入下一波。

边界：当前真实库只读，`org-org/dev-project` 唯一正向、`dev-org` 零副作用；不启 Host/worker/Provider，不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。Goal 保持 active。
