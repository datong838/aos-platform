# E17-s3o-w-ao-b24｜共享 Receipt 操作矩阵与伪发行反例

## 只读权威边界

- 已读 231-4、BIND-1 31、b12/b19/b22/b23、`aip6_002` 原表定义及当前生产写者。共享 RegistryReceipt 的已识别写者：AgentInstance create/update，SkillBinding create/update/evaluate，AgentRun create/cancel_queued，ExecutionAttempt create/状态衍生，Handoff issue/decision，CapabilityBinding create/update/evaluate。其他服务有不同 Receipt 写入函数，不能由本波矩阵断言已覆盖全部表或把普通 runtime 的共享表 INSERT 全撤。精确矩阵见 b24 plan。
- 当前真库仅只读：`aos_current_preview_20260927@a0v_135`，`org-org/dev-project` RegistryReceipt6（均 `agent_instance.create`）、CapabilityBinding0、正式 Capability issuer role0；`aos_runtime` 对共享 Receipt INSERT 与 CapabilityBinding INSERT/UPDATE 为 true，独立 DB CONNECT 为 false。故当前直接 runtime 登录仍被挡，但表级 operation 防伪未建，b20 预览写503继续是实例门。

## RED 与仅隔离库的修订

1. 在 b22 一次性全迁移 test DB 的真实独立 NOINHERIT issuer/runtime 登录测试中新增反例：Binding 从版本3更新为4并写合法 update Receipt 后，再插入额外 `capability_binding.create` Receipt。旧 `BEFORE INSERT` 守卫只核同事务 `xmin`/Binding ID/版本，测试 exit1，`DID NOT RAISE InsufficientPrivilege`。这是原探针的真实合同漏洞，不把旧 b22 GREEN 外推为操作类型安全。
2. 先在 b24 文件级 plan 增合同，再**仅在一次性 test DB**给 Binding 加数据库 BEFORE INSERT/UPDATE 覆写的 last-operation 探针列；Receipt 守卫改 deferred AFTER INSERT，在事务末查最终 Binding 版本、数据库派生的 operation 和当前事务行版本。增加先插伪 create 后 update、update 中伪 evaluate、手填标记伪 create 等负例；原 create/update/evaluate 与普通 runtime Agent/Skill/Run/Handoff Receipt 正向保留。目标加相邻 `AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py tests/aip/test_e17_s3owaob12_tool_receipt_identity_pg.py tests/aip/test_e17_s3ol_capability_issuer_pg.py tests/aip/test_aip6_003_exact_instance.py tests/aip/test_aip6_capability_run_handoff.py -k 'not downgrade'`：exit0，`14 passed, 1 deselected, 1 xfailed`；strict xfail 是原正式库无配对 Receipt 缺口。
3. 同组未排除旧降级测试时 exit1，`14 passed, 1 failed, 1 xfailed`；失败点是既有测试要从当前 `a0v_135` 降级，迁移明确抛 `shared schema receipt ACL cannot be silently widened`，本波未修改迁移。`py_compile` 与 `git diff --check` 均 exit0。当前原库再次只读核为135/Receipt6/Binding0/正式issuer0；API/Web生产代码和原库均无变化，故不重启、不把页面200作本波业务通过。

## 复审与下波

- 隔离探针现能拒绝已发现的额外 create/evaluate 伪回执和请求方标记篡改；仍不是可直接部署的迁移。生产方案须审查添加列的历史行兼容、状态/健康以外的 evaluate 分类、同一 Binding 一事务多写、触发器权限/RLS、旧合法 Receipt、撤销及 rollback、真实私有 issuer/OIDC/API 非 owner接线。`xmin` 仅用于事务内探针，不存作长期真源。
- 当前正式写入口继续503，Host/worker/Provider关，八配置/六 Binding/Owner/自然首链 pending。下一波 b25先冻结生产 migration/identity/rollback 合同及独立完整恢复克隆 RED，再最小代码；当前库迁移只能在新一致备份可恢复、零执行窗口与合法正式身份齐备后单独执行。`org-org/dev-project`唯一正向，`dev-org`零副作用，不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
